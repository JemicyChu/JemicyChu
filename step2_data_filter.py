import json
import pickle
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Literal, Tuple, Optional, Union
import gradio as gr # Added Gradio import
import traceback # For detailed error logging in Gradio

# Assuming model.py is in the same directory or Python path
from model import Record # Record class from model.py

# Define and create base output directory for cleaned datasets
BASE_OUTPUT_DIR = Path("cleaned_datasets")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Helper to sanitize filenames
def sanitize_filename(name_str: str) -> str:
    return "".join(c if c.isalnum() or c in (" ", ".", "_") else "_" for c in name_str).rstrip()

class DataSet:
    def __init__(self, name: str, records: List[Record] = None):
        self.name = name
        self.records: List[Record] = records if records else []
        self.cleaner = DataClean(self) # Initialize DataClean with this dataset
        self.load_errors: List[Tuple[str, str]] = [] # filename, error_message

    def load(self, file_path: Union[str, Path]) -> None:
        file_path_obj = Path(file_path)
        self.load_errors = [] # Reset errors on new load

        if file_path_obj.suffix == ".zip":
            self._load_from_zip(file_path_obj)
        elif file_path_obj.suffix == ".json":
            self._load_from_json([file_path_obj]) # Pass as list for consistency
        elif file_path_obj.suffix == ".pkl":
            self._load_from_pickle(file_path_obj)
        else:
            self.load_errors.append((file_path_obj.name, "Unsupported file type"))
            print(f"Error: Unsupported file type: {file_path_obj.name}")

        if self.load_errors:
            print(f"Encountered {len(self.load_errors)} error(s) during loading from {file_path_obj.name}.")
            # for err_file, err_msg in self.load_errors:
            #     print(f" - {err_file}: {err_msg}")
        print(f"Loaded {len(self.records)} records into dataset '{self.name}'.")


    def _load_from_json(self, json_files: List[Path]) -> None:
        for file_path_obj in json_files:
            try:
                with file_path_obj.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list): # Expect a list of records
                        for item in data:
                            try:
                                self.records.append(Record(**item))
                            except Exception as e: # Catch Pydantic validation errors or other issues
                                self.load_errors.append((file_path_obj.name, f"Error parsing record: {str(e)}"))
                    elif isinstance(data, dict): # Single record in a file
                         try:
                            self.records.append(Record(**data))
                         except Exception as e:
                            self.load_errors.append((file_path_obj.name, f"Error parsing record: {str(e)}"))
                    else:
                        self.load_errors.append((file_path_obj.name, "JSON content is not a list or a dictionary of records."))
            except json.JSONDecodeError as e:
                self.load_errors.append((file_path_obj.name, f"JSON Decode Error: {str(e)}"))
            except Exception as e:
                self.load_errors.append((file_path_obj.name, f"Unexpected error reading JSON: {str(e)}"))


    def _load_from_zip(self, file_path: Path) -> None:
        json_files_in_zip: List[Path] = []
        temp_extract_dir = None

        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Create a temporary directory for extraction if not already created by a previous call or if needed
                # For simplicity, let's assume Gradio provides a readable path, or we extract all JSONs.
                # If files are large, selective extraction or processing in memory would be better.
                
                # Option 1: Extract all JSON files to a temporary directory (simplest for now)
                temp_extract_dir = Path(file_path.stem + "_temp_extracted_json")
                temp_extract_dir.mkdir(parents=True, exist_ok=True)
                
                for member_name in zip_ref.namelist():
                    if member_name.endswith(".json"):
                        # Ensure the path is safe (no directory traversal)
                        # For this example, we assume benign filenames from our own Step 1.
                        # In a more robust system, sanitize member_name.
                        target_path = temp_extract_dir / Path(member_name).name # Flatten structure
                        with target_path.open('wb') as outfile, zip_ref.open(member_name) as infile:
                            outfile.write(infile.read())
                        json_files_in_zip.append(target_path)
                
                if json_files_in_zip:
                    self._load_from_json(json_files_in_zip)
                else:
                    self.load_errors.append((file_path.name, "No JSON files found in the ZIP archive."))

        except zipfile.BadZipFile:
            self.load_errors.append((file_path.name, "Invalid or corrupted ZIP file."))
        except Exception as e:
            self.load_errors.append((file_path.name, f"Error processing ZIP file: {str(e)}"))
        finally:
            # Clean up temporary directory if created
            if temp_extract_dir and temp_extract_dir.exists():
                for item in temp_extract_dir.iterdir():
                    item.unlink() # Delete files
                temp_extract_dir.rmdir() # Delete directory


    def _load_from_pickle(self, file_path: Path) -> None:
        try:
            with file_path.open('rb') as f:
                loaded_data = pickle.load(f)
                if isinstance(loaded_data, list) and all(isinstance(item, Record) for item in loaded_data):
                    self.records.extend(loaded_data)
                elif isinstance(loaded_data, DataSet): # If a whole DataSet object was pickled
                    self.records.extend(loaded_data.records)
                    # Potentially merge other attributes like name, if desired
                else:
                    self.load_errors.append((file_path.name, "Pickle file does not contain a list of Records or a DataSet object."))
        except pickle.UnpicklingError:
            self.load_errors.append((file_path.name, "Error unpickling data. File may be corrupted or not a pickle file."))
        except Exception as e:
            self.load_errors.append((file_path.name, f"Unexpected error reading pickle: {str(e)}"))


    def _sanitize_filename(self, name_str: str) -> str:
        return "".join(c if c.isalnum() or c in (" ", ".", "_") else "_" for c in name_str).rstrip()

    def save(self, filepath: Union[str, Path], save_type: Literal["csv", "json", "bytes", "pkl"] = "pkl") -> None:
        file_path_obj = Path(filepath)
        # Ensure parent directory exists
        file_path_obj.parent.mkdir(parents=True, exist_ok=True)

        if save_type == "pkl":
            self._save_to_pickle(file_path_obj)
        elif save_type == "json":
            self._save_to_json(file_path_obj)
        elif save_type == "csv": 
            self._save_to_csv(file_path_obj)
        # Removed "bytes" type as it was not implemented and not requested for this step
        else:
            print(f"Unsupported save type: {save_type}")
            # Potentially raise an error or handle more gracefully
            raise ValueError(f"Unsupported save type: {save_type}")

    def _save_to_pickle(self, filepath: Path) -> None:
        try:
            with filepath.open('wb') as f:
                pickle.dump(self.records, f)
            print(f"Dataset saved to {filepath} (PKL)")
        except Exception as e:
            print(f"Error saving to PKL {filepath}: {e}")
            raise # Re-raise after printing for Gradio to catch

    def _save_to_json(self, filepath: Path) -> None:
        try:
            with filepath.open('w', encoding='utf-8') as f:
                json.dump([record.model_dump(mode='json') for record in self.records], f, indent=4)
            print(f"Dataset saved to {filepath} (JSON)")
        except Exception as e:
            print(f"Error saving to JSON {filepath}: {e}")
            raise # Re-raise

    def _save_to_csv(self, filepath: Path) -> None:
        # Basic CSV saving example, requires self.records to be flat or specific fields chosen
        # This might need a library like pandas for robust CSV handling of complex objects
        import csv
        if not self.records:
            print(f"No records to save to CSV for {filepath}")
            return
        
        # Assuming records are Pydantic models, get field names from the first record
        # This is a simplification; ideally, ensure all records have same structure or define columns explicitly
        fieldnames = list(self.records[0].model_fields.keys())
        
        try:
            with filepath.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in self.records:
                    writer.writerow(record.model_dump()) # model_dump() is Pydantic v2
            print(f"Dataset saved to {filepath} (CSV)")
        except Exception as e:
            print(f"Error saving to CSV {filepath}: {e}")
            raise # Re-raise

    def run(self, save_output: bool = False, output_filepath: Optional[Union[str, Path]] = None, save_type: Literal["csv", "json", "pkl"] = "pkl"):
        print(f"Running DataClean on dataset: {self.name}")
        self.cleaner.process_all() 
        
        summary = self.cleaner.get_summary() # Get summary from cleaner
        summary_str = ", ".join([f"{k}: {v}" for k,v in summary.items()])
        print(f"DataClean finished for dataset: {self.name}. Summary: {summary_str}")

        if save_output:
            if not output_filepath:
                # Default filepath if not provided, using sanitized name and BASE_OUTPUT_DIR
                # This case should ideally be handled by the caller (like Gradio UI)
                sanitized_name = self._sanitize_filename(self.name)
                output_filepath = BASE_OUTPUT_DIR / f"{sanitized_name}_cleaned.{save_type}"
            
            self.save(filepath=output_filepath, save_type=save_type)
        
        return summary # Return summary for potential use in UI

class DataClean:
    def __init__(self, dataset: DataSet):
        self.dataset = dataset
        self.stats = {"empty_text_removed": 0, "short_text_removed": 0, "classified_as_control": 0} # Example stats

    def remove_empty_text_or_desc(self) -> None:
        original_count = len(self.dataset.records)
        # Remove records where node_data.text and node_data.description are both None or empty
        self.dataset.records = [
            r for r in self.dataset.records 
            if not (
                r.selection_details and r.selection_details.node_data and
                (r.selection_details.node_data.text is None or r.selection_details.node_data.text.strip() == "") and
                (r.selection_details.node_data.description is None or r.selection_details.node_data.description.strip() == "")
            )
        ]
        removed_count = original_count - len(self.dataset.records)
        self.stats["empty_text_removed"] = removed_count
        print(f"Removed {removed_count} records with empty text and description.")

    def remove_short_text(self, min_length: int = 3) -> None:
        original_count = len(self.dataset.records)
        # Remove records where node_data.text is shorter than min_length
        # (Considering only text, not description for this rule)
        self.dataset.records = [
            r for r in self.dataset.records
            if not (
                r.selection_details and r.selection_details.node_data and
                r.selection_details.node_data.text and
                len(r.selection_details.node_data.text.strip()) < min_length
            )
        ]
        removed_count = original_count - len(self.dataset.records)
        self.stats["short_text_removed"] = removed_count
        print(f"Removed {removed_count} records with text shorter than {min_length} characters.")

    def classify_potential_control_elements(self) -> None:
        # Example: Classify elements as 'control' if they have a resource_id and specific class names
        # This is a placeholder for more complex classification logic
        count = 0
        control_keywords = ["button", "checkbox", "switch", "imagebutton", "edittext", "spinner"] # Common Android widget class name parts
        for record in self.dataset.records:
            if record.selection_details and record.selection_details.node_data:
                node = record.selection_details.node_data
                # Add a 'classification' field to node_data if it doesn't exist
                if not hasattr(node, 'classification'):
                     # This modification would require 'classification' to be added to NodeData Pydantic model
                     # For now, let's assume we add it to raw_attributes or a temporary spot if NodeData is strict
                     pass # node.classification = "unknown" 
                
                is_control = False
                if node.resource_id: # Must have a resource_id
                    if node.class_name and any(keyword in node.class_name.lower() for keyword in control_keywords):
                        is_control = True
                    # elif node.description and any(keyword in node.description.lower() for keyword in ["tap", "click", "select"]): # Less reliable
                    # is_control = True
                
                if is_control:
                    # node.classification = "control_element" # Example of setting classification
                    count += 1
        self.stats["classified_as_control"] = count
        print(f"Classified {count} records as potential control elements.")

    def process_all(self) -> None:
        print("Starting data cleaning process...")
        self.remove_empty_text_or_desc()
        self.remove_short_text(min_length=2) # Example: min length of 2
        self.classify_potential_control_elements()
        print("Data cleaning process finished.")
        print(f"Cleaning Stats: {self.stats}")

    def get_summary(self):
        return self.stats

# --- Gradio UI and Application Logic ---
def process_and_clean_dataset(uploaded_file_obj, output_filename_str):
    if uploaded_file_obj is None:
        return "Error: No dataset file provided. <br> Output Path: N/A" # HTML for line break

    input_path = uploaded_file_obj.name # Path to the uploaded temp file by Gradio
    
    status_messages = []
    status_messages.append(f"Processing: `{Path(input_path).name}`")

    if not output_filename_str.strip():
        # Create a default output filename based on input, ensure it's within BASE_OUTPUT_DIR
        output_filename_str = f"cleaned_{Path(input_path).stem}.pkl"
    
    if not output_filename_str.endswith((".pkl", ".json", ".csv")): # Allow multiple save types
        # Default to .pkl if no valid extension or an unsupported one is given
        status_messages.append(f"Warning: Output filename '{output_filename_str}' does not have a supported extension (.pkl, .json, .csv). Defaulting to .pkl.")
        output_filename_str = Path(output_filename_str).stem + ".pkl"

    # Determine save type from filename extension
    save_type_str = Path(output_filename_str).suffix[1:] #.pkl -> pkl
    if save_type_str not in ["pkl", "json", "csv"]:
        status_messages.append(f"Warning: Unsupported save type '{save_type_str}' in filename. Defaulting to 'pkl'.")
        save_type_str = "pkl"
        output_filename_str = Path(output_filename_str).stem + ".pkl"


    # Ensure output_filename_str is just a name, not a path, then join with BASE_OUTPUT_DIR
    output_file_path = BASE_OUTPUT_DIR / Path(output_filename_str).name 
    output_file_path.parent.mkdir(parents=True, exist_ok=True) # Ensure output dir exists

    try:
        status_messages.append(f"Attempting to load dataset...")
        dataset = DataSet(name=f"dataset_from_{Path(input_path).stem}")
        dataset.load(input_path) 

        if not dataset.records:
            status_messages.append("Warning: No records found in the dataset after loading.")
            if dataset.load_errors:
                errors_str = "<br>".join([f"&nbsp;&nbsp;- {err[0]}: {err[1][:100]}..." for err in dataset.load_errors[:5]]) # Limit errors displayed
                status_messages.append(f"Load errors:<br>{errors_str}")
            return "<br>".join(status_messages)

        status_messages.append(f"Successfully loaded {len(dataset.records)} records.")
        status_messages.append("Starting data cleaning and classification...")
        
        # dataset.run now returns the summary
        cleaning_summary_dict = dataset.run(save_output=False) # save_output=False as we save explicitly after this
        
        summary_str = "<br>".join([f"&nbsp;&nbsp;- {k.replace('_', ' ').capitalize()}: {v}" for k,v in cleaning_summary_dict.items()])
        status_messages.append(f"Cleaning summary:<br>{summary_str}")
        status_messages.append("Cleaning and classification complete.")

        # Save the cleaned dataset to the specified path with determined save_type
        dataset.save(filepath=output_file_path, save_type=save_type_str) 
        
        status_messages.append(f"**Success!** Cleaned dataset saved to: `{output_file_path}` (Type: {save_type_str.upper()})")
        
        return "<br>".join(status_messages) 

    except Exception as e:
        status_messages.append(f"<br>**An error occurred:** {str(e)}")
        tb_str = traceback.format_exc()
        status_messages.append(f"```\n{tb_str}\n```") # Format traceback for Markdown
        return "<br>".join(status_messages)

if __name__ == '__main__':
    # BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True) # Ensure output dir exists

    # with gr.Blocks(theme=gr.themes.Soft()) as app_cleaner:
    #     gr.Markdown("# Dataset Cleaning Service (Step 2)")
    #     gr.Markdown("Upload a dataset (ZIP from Step 1, or a PKL/JSON/CSV file). The service will clean it and save the result in the `cleaned_datasets` directory.")
        
    #     with gr.Row():
    #         input_file_gr = gr.File(label="Upload Dataset (ZIP, PKL, JSON, CSV)", type="filepath")
        
    #     output_filename_gr = gr.Textbox(
    #         label="Output Filename for Cleaned Data (e.g., cleaned_data.pkl, my_output.json). Extension determines save type.", 
    #         placeholder="e.g., cleaned_my_data.pkl",
    #         value="cleaned_output.pkl" # Default value
    #     )
        
    #     run_button_gr = gr.Button("🧹 Run Cleaning and Save", variant="primary")
        
    #     gr.Markdown("---") # Separator
    #     status_display_gr = gr.Markdown("### Status & Results") # Using Markdown for status

    #     run_button_gr.click(
    #         fn=process_and_clean_dataset,
    #         inputs=[input_file_gr, output_filename_gr],
    #         outputs=[status_display_gr] 
    #     )

    # app_cleaner.launch(debug=True, share=False) # Commented out for importability
    print("step2_data_filter.py can now be imported as a module.")
    print("To run its original Gradio app, uncomment the relevant lines in if __name__ == '__main__': and run this script directly.")

```
