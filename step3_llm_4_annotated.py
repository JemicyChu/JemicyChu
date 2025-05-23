import gradio as gr
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import pickle # For loading PKL directly
import zipfile # For loading ZIPs
import traceback

# Assuming model.py is in the same directory or Python path
from model import Record, DeviceAndAppEnvironment, SelectionDetails, NodeData, ImageUrls

# --- Global State Variables ---
ui_records_list_val: List[Dict[str, Any]] = [] # Holds all records prepared for UI
current_idx_val: int = -1
output_csv_path_val: Optional[Path] = None
loaded_dataset_path_val: Optional[Path] = None

# --- Configuration ---
BASE_OUTPUT_DIR = Path("annotated_data")
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Helper Functions ---
def safe_get(data_dict, key, default=""):
    """Safely get a value from a dictionary or Pydantic model."""
    if isinstance(data_dict, dict):
        return data_dict.get(key, default)
    # For Pydantic models, hasattr and getattr can be used, but direct access is fine if structure is known
    # This basic helper assumes dict-like access or that the key exists.
    # A more robust version would check type and use getattr for Pydantic models.
    return getattr(data_dict, key, default) if hasattr(data_dict, key) else default

# --- Core Functions ---
def load_and_process_dataset_records(dataset_file_obj: Any, existing_csv_file_obj: Optional[Any]) -> Tuple[List[Dict[str, Any]], int, str, str, List[Any]]:
    global ui_records_list_val, current_idx_val, output_csv_path_val, loaded_dataset_path_val
    
    ui_records_list_val = []
    current_idx_val = -1
    load_status = ""
    initial_record_display = ["", "", "", "", gr.update(value=None, visible=False), ""] # Placeholder for actual fields
    # This list needs to be expanded to match ALL outputs of get_display_for_record, including new device fields
    # For now, this is a conceptual placeholder. The actual list will be much longer.
    num_main_outputs = 6 # screenshot_display, ui_element_details_display, current_record_text, system_prompt_input, llm_answer_input, annotation_status_text
    num_device_outputs = 8 # model, brand, sys_ver, sdk_ver, font, dark_mode, pkg, category
    num_device_buttons = 2 # edit, lock
    
    # Simplified initial state for all outputs (empty/non-interactive)
    initial_ui_state = [gr.update(value="", interactive=False)] * (num_main_outputs + num_device_outputs + num_device_buttons)
    initial_ui_state[4] = gr.update(value=None, visible=False, interactive=False) # screenshot_display is an Image
    initial_ui_state[num_main_outputs + num_device_outputs] = gr.update(interactive=False) # edit button
    initial_ui_state[num_main_outputs + num_device_outputs + 1] = gr.update(interactive=False) # lock button


    if not dataset_file_obj:
        return initial_ui_state + ["Error: No dataset file provided.", ""]

    try:
        input_path = Path(dataset_file_obj.name)
        loaded_dataset_path_val = input_path
        load_status = f"Loading dataset: {input_path.name}\n"
        raw_records = []
        load_errors = []

        if input_path.suffix == ".pkl":
            with input_path.open('rb') as f:
                loaded_data = pickle.load(f)
                if isinstance(loaded_data, list) and all(isinstance(item, Record) for item in loaded_data):
                    raw_records = loaded_data
                else:
                    load_status += "Error: PKL file does not contain a list of Record objects."
                    return initial_ui_state + [load_status, ""]
        elif input_path.suffix == ".zip":
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                for member_name in zip_ref.namelist():
                    if member_name.endswith(".json"):
                        try:
                            with zip_ref.open(member_name) as json_file:
                                record_dict = json.load(json_file)
                                raw_records.append(Record(**record_dict)) # Validate with Pydantic
                        except Exception as e:
                            load_errors.append(f"Error loading {member_name}: {e}")
            if load_errors:
                load_status += "\n".join(load_errors)
        else:
            load_status += "Error: Unsupported dataset file type. Please use .pkl or .zip."
            return initial_ui_state + [load_status, ""]

        if not raw_records:
            load_status += "No records found in the dataset."
            return initial_ui_state + [load_status, ""]

        # Determine output CSV path
        if existing_csv_file_obj:
            output_csv_path_val = Path(existing_csv_file_obj.name)
            load_status += f"Using existing CSV: {output_csv_path_val.name}\n"
            # Load existing annotations if CSV is provided
            # For simplicity, this part is not fully implemented here but would merge based on record ID
        else:
            timestamp = Path(input_path.stem).name # Use stem of input file for output name
            output_csv_path_val = BASE_OUTPUT_DIR / f"annotations_{timestamp}.csv"
            load_status += f"New CSV will be: {output_csv_path_val.name}\n"
        
        output_csv_path_val.parent.mkdir(parents=True, exist_ok=True)

        # Process records for UI
        for i, record_obj_raw in enumerate(raw_records):
            # record_obj_raw is an instance of Record
            device_env_data = {}
            device_serial = "unknown_serial"
            capture_timestamp_str = record_obj_raw.capture_timestamp if hasattr(record_obj_raw, 'capture_timestamp') and record_obj_raw.capture_timestamp else record_obj_raw.session_id # Fallback to session_id if capture_timestamp is missing
            
            if record_obj_raw.device_and_app_environment:
                device_env_data = record_obj_raw.device_and_app_environment.model_dump()
                if record_obj_raw.device_and_app_environment.serial:
                    device_serial = record_obj_raw.device_and_app_environment.serial
            
            record_identifier = f"{device_serial}_{capture_timestamp_str}"

            img_url = None
            if record_obj_raw.image_urls and record_obj_raw.image_urls.raw_image_url: # Prefer raw_image_url
                img_url = str(record_obj_raw.image_urls.raw_image_url)
            elif record_obj_raw.selection_details and record_obj_raw.selection_details.image_evidence and record_obj_raw.selection_details.image_evidence.raw_image_url: # Fallback
                img_url = str(record_obj_raw.selection_details.image_evidence.raw_image_url)

            details_str = "UI Element Details:\n"
            if record_obj_raw.selection_details and record_obj_raw.selection_details.node_data:
                node = record_obj_raw.selection_details.node_data
                details_str += f"  Text: {node.text or 'N/A'}\n"
                details_str += f"  Content Desc: {node.description or 'N/A'}\n"
                details_str += f"  Class: {node.class_name or 'N/A'}\n"
                details_str += f"  Resource ID: {node.resource_id or 'N/A'}\n"
                details_str += f"  Package: {node.package_name or 'N/A'}\n"
                details_str += f"  XPath: {node.x_path or 'N/A'}\n"
                if record_obj_raw.selection_details.element_bounds:
                     details_str += f"  Element Bounds: {record_obj_raw.selection_details.element_bounds}\n"
            else:
                details_str = "No specific UI element selection details available."

            ui_records_list_val.append({
                "id": record_identifier, # Use the new robust identifier
                "screenshot_url": img_url,
                "ui_element_details": details_str,
                "device_env_data": device_env_data,
                # Store the Pydantic model itself for easier access to original structured data later
                "_original_record_obj": record_obj_raw, 
                # Fallback for _original_record_raw if needed for direct JSON dump (as before)
                "_original_record_raw_json_dump": record_obj_raw.model_dump(mode='json'),
                "llm_prompt": "", "llm_answer": "", "user_annotation": "" 
            })

        current_idx_val = 0
        load_status += f"Successfully processed {len(ui_records_list_val)} records.\n"
        
        # Call get_display_for_record to populate the first record's data
        # This requires all UI components to be defined globally or passed around.
        # For now, returning the state and letting Gradio handle the UI update flow.
        if ui_records_list_val:
             # This is where the full list of gr.update() calls from get_display_for_record would be returned
            # For now, just returning a success status and the first record's text
            # This will be fully implemented when get_display_for_record is fully defined with all outputs
            first_record_display = get_display_for_record(current_idx_val)
            return first_record_display + [load_status, str(output_csv_path_val)]
        else:
            return initial_ui_state + [load_status, "No records to display."]


    except Exception as e:
        load_status += f"An error occurred during loading: {str(e)}\n{traceback.format_exc()}"
        return initial_ui_state + [load_status, ""]


def get_display_for_record(record_idx: int) -> List[Any]:
    if not ui_records_list_val or record_idx < 0 or record_idx >= len(ui_records_list_val):
        # Return updates for all UI elements to clear them or show an error/empty state
        # This needs to match the full list of outputs for nav/load buttons
        num_main_outputs = 6 
        num_device_outputs = 8
        num_device_buttons = 2
        empty_state = [gr.update(value="", interactive=False)] * (num_main_outputs + num_device_outputs + num_device_buttons)
        empty_state[0] = gr.update(value=None, visible=False, interactive=False) # screenshot
        empty_state[num_main_outputs + num_device_outputs] = gr.update(interactive=False) # edit button
        empty_state[num_main_outputs + num_device_outputs + 1] = gr.update(interactive=False) # lock button
        return empty_state

    record_data = ui_records_list_val[record_idx]
    
    # Device env data population (assuming keys match model.py)
    dev_env = record_data.get("device_env_data", {})
    
    # This list must match the order of outputs for navigation/load buttons
    return [
        gr.update(value=record_data.get("screenshot_url"), visible=bool(record_data.get("screenshot_url"))),
        gr.update(value=record_data.get("ui_element_details", "")),
        gr.update(value=f"Record {record_idx + 1} of {len(ui_records_list_val)} (ID: {record_data.get('id')})"),
        gr.update(value=record_data.get("llm_prompt", "")), # system_prompt_input
        gr.update(value=record_data.get("llm_answer", "")), # llm_answer_input
        gr.update(value=""), # annotation_status_text (clear on new record)
        
        # Device Info Textboxes (interactive=False initially, controlled by edit/lock)
        gr.update(value=safe_get(dev_env, 'model'), interactive=False),
        gr.update(value=safe_get(dev_env, 'brand'), interactive=False),
        gr.update(value=safe_get(dev_env, 'system_version'), interactive=False),
        gr.update(value=safe_get(dev_env, 'sdk_version'), interactive=False),
        gr.update(value=str(safe_get(dev_env, 'font_scale', 'N/A')), interactive=False),
        gr.update(value=str(safe_get(dev_env, 'dark_mode_enabled', 'unknown')), interactive=False),
        gr.update(value=safe_get(dev_env, 'package_name'), interactive=False),
        gr.update(value=safe_get(dev_env, 'app_category'), interactive=False),
        
        # Device Info Buttons
        gr.update(interactive=True), # edit_device_info_button_gr
        gr.update(interactive=False) # lock_device_info_button_gr
    ]

def handle_prev_click(current_idx: int) -> List[Any]:
    global current_idx_val
    if not ui_records_list_val: return get_display_for_record(-1) # Should match all outputs
    current_idx_val = max(0, current_idx - 1)
    return get_display_for_record(current_idx_val)

def handle_next_click(current_idx: int) -> List[Any]:
    global current_idx_val
    if not ui_records_list_val: return get_display_for_record(-1) # Should match all outputs
    current_idx_val = min(len(ui_records_list_val) - 1, current_idx + 1)
    return get_display_for_record(current_idx_val)

# Placeholder for toggle_device_info_edit_mode
def toggle_device_info_edit_mode(is_editable: bool) -> List[Any]:
    # This will return gr.update for all device textboxes and the edit/lock buttons
    # Number of device textboxes = 8
    updates = [gr.update(interactive=is_editable)] * 8 
    updates.append(gr.update(interactive=not is_editable)) # Edit button
    updates.append(gr.update(interactive=is_editable))   # Lock button
    return updates


# Placeholder for save_annotation and collect_and_save_annotation
def collect_and_save_annotation(
    current_idx_from_ui: int, # Or use global current_idx_val
    llm_prompt: str, llm_answer: str, user_annotation_final: str,
    # Add new device info fields from UI here
    dev_model: str, dev_brand: str, dev_system_version: str, dev_sdk_version: str,
    dev_font_scale: str, dev_dark_mode: str, dev_pkg_name: str, dev_app_category: str
) -> str:
    global current_idx_val # Ensure global is used if not relying on current_idx_from_ui
    
    if current_idx_val < 0 or current_idx_val >= len(ui_records_list_val):
        return "Error: No valid record selected for saving."
    
    try:
        # Call the main save_annotation logic
        status = save_annotation(
            current_idx_val, llm_prompt, llm_answer, user_annotation_final,
            dev_model, dev_brand, dev_system_version, dev_sdk_version,
            dev_font_scale, dev_dark_mode, dev_pkg_name, dev_app_category
        )
        return status
    except Exception as e:
        return f"Error saving annotation: {str(e)}\n{traceback.format_exc()}"

def save_annotation(
    record_idx: int, llm_prompt: str, llm_answer: str, user_annotation_final: str,
    # Add new device info fields here
    dev_model_ui: str, dev_brand_ui: str, dev_system_version_ui: str, dev_sdk_version_ui: str,
    dev_font_scale_ui: str, dev_dark_mode_ui: str, dev_pkg_name_ui: str, dev_app_category_ui: str
) -> str:
    global ui_records_list_val, output_csv_path_val

    if not output_csv_path_val:
        return "Error: Output CSV path not set. Load a dataset first."

    current_record_ui_data = ui_records_list_val[record_idx]
    
    # Update device_env_data
    original_device_env_dict = current_record_ui_data.get("device_env_data", {})
    # Create a copy to modify
    updated_device_env_dict = original_device_env_dict.copy()
    
    # Update with values from UI
    updated_device_env_dict['model'] = dev_model_ui
    updated_device_env_dict['brand'] = dev_brand_ui
    updated_device_env_dict['system_version'] = dev_system_version_ui
    updated_device_env_dict['sdk_version'] = dev_sdk_version_ui
    # Handle potential type conversion for font_scale (float or str)
    try:
        updated_device_env_dict['font_scale'] = float(dev_font_scale_ui)
    except ValueError:
        updated_device_env_dict['font_scale'] = dev_font_scale_ui # Keep as string if not float
    updated_device_env_dict['dark_mode_enabled'] = dev_dark_mode_ui
    updated_device_env_dict['package_name'] = dev_pkg_name_ui
    updated_device_env_dict['app_category'] = dev_app_category_ui
    
    # Validate and serialize the updated device environment data
    try:
        device_env_pydantic_obj = DeviceAndAppEnvironment(**updated_device_env_dict)
        device_env_json_for_csv = device_env_pydantic_obj.model_dump_json()
        # Update in-memory store with validated and dumped dict (consistent representation)
        ui_records_list_val[record_idx]['device_env_data'] = device_env_pydantic_obj.model_dump()
    except Exception as e: # Pydantic validation error
        return f"Error validating device info: {str(e)}. Annotation not saved."

    # Prepare data for CSV
    # Retrieve the original Record Pydantic model object
    original_record_obj: Optional[Record] = current_record_ui_data.get("_original_record_obj")
    
    image_urls_json_str = "{}"
    selection_details_json_str = "{}"

    if original_record_obj:
        if original_record_obj.image_urls:
            image_urls_json_str = original_record_obj.image_urls.model_dump_json()
        if original_record_obj.selection_details:
            selection_details_json_str = original_record_obj.selection_details.model_dump_json()

    output_data = {
        "record_id": current_record_ui_data.get("id"), # This is now the robust identifier
        "image_urls_json": image_urls_json_str,
        "selection_details_json": selection_details_json_str,
        "device_and_app_environment_json": device_env_json_for_csv, # Potentially modified
        "llm_prompt": llm_prompt,
        "llm_answer": llm_answer,
        "user_annotation_final": user_annotation_final,
        "full_original_record_json": json.dumps(current_record_ui_data.get("_original_record_raw_json_dump", {})), # Renamed, uses the JSON dump
        "annotation_timestamp": pd.Timestamp.now().isoformat(),
    }
    
    # Update in-memory store for these fields too
    ui_records_list_val[record_idx]["llm_prompt"] = llm_prompt
    ui_records_list_val[record_idx]["llm_answer"] = llm_answer
    ui_records_list_val[record_idx]["user_annotation"] = user_annotation_final

    # Save to CSV
    df_new_row = pd.DataFrame([output_data])
    if output_csv_path_val.exists():
        df_existing = pd.read_csv(output_csv_path_val)
        # Avoid duplicates by record_id, update if exists
        df_existing = df_existing[df_existing['record_id'] != output_data['record_id']]
        df_to_save = pd.concat([df_existing, df_new_row], ignore_index=True)
    else:
        df_to_save = df_new_row
    
    df_to_save.to_csv(output_csv_path_val, index=False)
    return f"Annotation for record {current_record_ui_data.get('id')} saved to {output_csv_path_val.name}"


# --- Gradio UI Definition ---
with gr.Blocks(theme=gr.themes.Glass()) as app:
    gr.Markdown("# LLM-Powered UI Element Annotator (Step 3)")

    # Outputs list for navigation and load buttons - MUST BE KEPT IN SYNC WITH get_display_for_record
    # Plus status_text_load, output_csv_path_display_gr
    all_ui_outputs_for_nav_load = [] 

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 1. Load Dataset")
            dataset_file_input = gr.File(label="Upload Dataset (PKL or ZIP from Step 1/2)")
            existing_csv_input = gr.File(label="Upload Existing Annotation CSV (Optional)")
            load_dataset_button = gr.Button("🚀 Load Dataset")
            status_text_load = gr.Markdown("Status: Not loaded.")
            output_csv_path_display_gr = gr.Textbox(label="Output CSV Path", interactive=False)

        with gr.Column(scale=2):
            gr.Markdown("## 2. Annotate Record")
            current_record_text = gr.Textbox(label="Current Record", interactive=False)
            screenshot_display = gr.Image(label="Screenshot", type="filepath", visible=False, interactive=False)
            ui_element_details_display = gr.Textbox(label="UI Element Details (from Record)", lines=5, interactive=False)

            # Device Info Section
            gr.Markdown("### Device Information (Loaded from Record)")
            with gr.Row():
                edit_device_info_button_gr = gr.Button("✏️ Edit Device Info", interactive=False)
                lock_device_info_button_gr = gr.Button("🔒 Lock Device Info", interactive=False)

            dev_model_gr = gr.Textbox(label="Device Model", interactive=False)
            dev_brand_gr = gr.Textbox(label="Device Brand", interactive=False)
            dev_system_version_gr = gr.Textbox(label="System Version", interactive=False)
            dev_sdk_version_gr = gr.Textbox(label="SDK Version (String)", interactive=False)
            dev_font_scale_gr = gr.Textbox(label="Font Scale (float or str)", interactive=False)
            dev_dark_mode_gr = gr.Textbox(label="Dark Mode (str: true/false/unknown)", interactive=False)
            dev_pkg_name_gr = gr.Textbox(label="Package Name", interactive=False)
            dev_app_category_gr = gr.Textbox(label="App Category", interactive=False)
            
            # List of device UI textboxes for easier handling in toggle function
            device_info_textboxes_gr = [
                dev_model_gr, dev_brand_gr, dev_system_version_gr, dev_sdk_version_gr,
                dev_font_scale_gr, dev_dark_mode_gr, dev_pkg_name_gr, dev_app_category_gr
            ]
            device_info_buttons_gr = [edit_device_info_button_gr, lock_device_info_button_gr]


            gr.Markdown("### LLM Assistance & Final Annotation")
            system_prompt_input = gr.Textbox(label="System Prompt for LLM (Pre-filled, Editable)", lines=3, value="You are a UI annotation assistant. Given the UI element details, suggest a concise, descriptive label and a category.")
            # In a real app, a button would trigger LLM call. Here, it's manual entry.
            llm_answer_input = gr.Textbox(label="LLM Suggested Answer (Manually copy/paste or type)", lines=3)
            user_annotation_final_input = gr.Textbox(label="✅ Your Final Annotation Label (Confirm or Edit LLM Suggestion)", lines=2)
            
            with gr.Row():
                prev_record_button = gr.Button("⬅️ Previous Record")
                next_record_button = gr.Button("➡️ Next Record")
            save_annotation_button = gr.Button("💾 Save Annotation for This Record", variant="primary")
            annotation_status_text = gr.Textbox(label="Annotation Status", interactive=False)

    # Define all_ui_outputs_for_nav_load (must match get_display_for_record's return structure)
    all_ui_outputs_for_nav_load = [
        screenshot_display, ui_element_details_display, current_record_text,
        system_prompt_input, llm_answer_input, annotation_status_text
    ] + device_info_textboxes_gr + device_info_buttons_gr


    # --- Event Handlers ---
    load_dataset_button.click(
        fn=load_and_process_dataset_records,
        inputs=[dataset_file_input, existing_csv_input],
        outputs=all_ui_outputs_for_nav_load + [status_text_load, output_csv_path_display_gr]
    )
    
    prev_record_button.click(
        fn=lambda: handle_prev_click(current_idx_val), # Use global current_idx_val
        inputs=[], 
        outputs=all_ui_outputs_for_nav_load
    )

    next_record_button.click(
        fn=lambda: handle_next_click(current_idx_val), # Use global current_idx_val
        inputs=[],
        outputs=all_ui_outputs_for_nav_load
    )
    
    edit_device_info_button_gr.click(
        fn=lambda: toggle_device_info_edit_mode(True),
        inputs=None,
        outputs=device_info_textboxes_gr + device_info_buttons_gr
    )
    
    lock_device_info_button_gr.click(
        fn=lambda: toggle_device_info_edit_mode(False),
        inputs=None,
        outputs=device_info_textboxes_gr + device_info_buttons_gr
    )

    save_annotation_button.click(
        fn=collect_and_save_annotation,
        inputs=[
            current_record_text, # This is a Textbox, not the index. Need to rely on global current_idx_val
            system_prompt_input, llm_answer_input, user_annotation_final_input
        ] + device_info_textboxes_gr, # Add device info textboxes as inputs
        outputs=[annotation_status_text]
    )

if __name__ == "__main__":
    app.launch(debug=True, share=False)
