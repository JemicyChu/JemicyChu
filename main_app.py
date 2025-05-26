import gradio as gr
from pathlib import Path
import sys

# --- Add project root to sys.path to allow for module imports ---
# This assumes main_app.py is at the root of the project or that this path adjustment is correct for the execution environment.
# In a real deployment, packaging or environment variables (PYTHONPATH) would handle this.
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError: # __file__ is not defined if running in some interactive environments like a raw Python interpreter
    project_root = Path.cwd() # Fallback to current working directory
    if str(project_root) not in sys.path:
         sys.path.insert(0, str(project_root))

print(f"Project root (or CWD) added to sys.path: {project_root}")
print(f"Current sys.path: {sys.path}")


# --- Attempt to import components from other modules ---
try:
    from model import Record, DeviceAndAppEnvironment, SelectionDetails, NodeData, ImageUrls
    print("Successfully imported from model.py")
    
    # AndroidDevice.py is expected to have classes/functions, not a Gradio app itself
    from AndroidDevice import AndroidPage, upload_file
    print("Successfully imported from AndroidDevice.py")
    
    # step1_data_store.py will have its Gradio app structure, but we'll use its class or functions
    # For now, let's assume we might import its core class if needed, or its UI definition function
    from step1_data_store import AndroidGradioApp # Assuming this class encapsulates Step 1 logic
    print("Successfully imported from step1_data_store.py")

    # step2_data_filter.py
    from step2_data_filter import DataSet, DataClean # And potentially the process_and_clean_dataset function
    print("Successfully imported from step2_data_filter.py")

    # step3_llm_4_annotated.py
    # For Step 3, we might import its core functions or UI building logic
    # We will copy and adapt functions from step3_llm_4_annotated.py directly into main_app.py for this integration.
    # This avoids complex refactoring of step3_llm_4_annotated.py to handle both standalone and imported states.
    # Key functions from step3 like load_and_process_dataset_records, get_display_for_record, etc., will be adapted here.
    import pandas as pd # For Step 3 saving logic
    import pickle # For Step 3 loading
    import zipfile # For Step 3 loading
    # model.Record, model.DeviceAndAppEnvironment etc. are already imported.
    print("Imports for Step 3 (pandas, pickle, zipfile) confirmed/added.")

    import traceback # Ensure traceback is imported for error handling
    from pathlib import Path # Ensure Path is imported

except ModuleNotFoundError as e:
    print(f"Error importing modules: {e}")
    # In a real app, might re-raise or handle more gracefully
    # For this task, printing the error is sufficient for diagnostics
    # sys.exit(1) # Optional: exit if critical modules are missing
except ImportError as e:
    print(f"ImportError: {e}. This might be due to circular dependencies or issues within the modules themselves.")
    # sys.exit(1) # Optional: exit

# --- Instantiate Step-specific App Logic Classes ---
step1_app_instance = AndroidGradioApp()
# step2_dataset_instance = DataSet(name="Step2Dataset") # If needed for more complex state, but functions might be enough
# step3_app_instance = ... # For Step 3 integration


# --- Define and Create Base Output Directories ---
# These should ideally match what's used in the individual step scripts if they also create outputs.
# For a unified app, it's good to have them defined centrally or passed as config.
Path("collected_data").mkdir(parents=True, exist_ok=True) # From step1
Path("cleaned_datasets").mkdir(parents=True, exist_ok=True) # From step2
Path("annotated_data").mkdir(parents=True, exist_ok=True)   # From step3
# General output directory for main_app if needed for combined outputs or reports
Path("main_app_outputs").mkdir(parents=True, exist_ok=True)


# --- Main Gradio Application UI ---
with gr.Blocks(theme=gr.themes.Soft(), title="Unified UI Data Processing App") as main_app_ui:
    gr.Markdown("# Unified UI Data Processing and Annotation Pipeline")

    # Placeholders for output file paths from each step
    # These will be updated by the respective step's logic when integrated
    with gr.Accordion("Cross-Step Data Handoff (Output Paths)", open=False):
        step1_output_display_gr = gr.Textbox(label="Step 1 Output (e.g., ZIP/PKL path)", interactive=False)
        step2_output_display_gr = gr.Textbox(label="Step 2 Output (e.g., Cleaned PKL path)", interactive=False)
        step3_output_display_gr = gr.Textbox(label="Step 3 Output (e.g., Annotation CSV path)", interactive=False)

    # Define State variables for data handoff
    # Define State variables for data handoff
    state_step1_output_zip_path = gr.State(None)
    state_step2_output_pkl_path = gr.State(None) 
    state_step3_output_csv_path = gr.State(None) # For Step 3 output CSV path
    state_step3_ui_records = gr.State([])        # To hold the list of records for annotation in Tab 3
    state_step3_current_index = gr.State(-1)     # Current record index for Tab 3

    with gr.Tabs():
        with gr.TabItem("1. Data Construction (Device Interaction)"):
            # ... (Existing Step 1 UI and logic - unchanged) ...
            gr.Markdown("## Tab 1: Device Data Collection and Storage (from `step1_data_store.py`)")
            step1_status_text = gr.Textbox(label="Status", interactive=False, lines=1, value="Connect to device to begin.")
            with gr.Tabs():
                with gr.TabItem("📱 Device Connection & Capture"):
                    with gr.Row():
                        step1_ip_port_input = gr.Textbox(label="Device IP:Port (e.g., 192.168.1.100:7912 or ADB serial)", value="127.0.0.1:5555")
                        step1_connect_btn = gr.Button("🔌 Connect to Device")
                    step1_capture_btn = gr.Button("📸 Capture Screenshot & UI XML")
                    with gr.Row():
                        step1_img_annotated_display = gr.Image(label="Current Screen (Annotated)", type="filepath", interactive=False)
                        step1_raw_img_url_hidden = gr.Textbox(label="Raw Image URL", visible=False) 
                    gr.Markdown("### Select UI Element from Hierarchy")
                    step1_node_dropdown = gr.Dropdown(label="Select UI Element", choices=[], interactive=True)
                    step1_element_details_display = gr.Textbox(label="Selected Element Details", lines=10, interactive=False)
                    step1_selected_bounds_hidden = gr.Textbox(visible=False)
                    step1_selected_xpath_hidden = gr.Textbox(visible=False)
                    step1_selected_resource_id_hidden = gr.Textbox(visible=False)
                    step1_selected_text_hidden = gr.Textbox(visible=False)
                    step1_selected_content_desc_hidden = gr.Textbox(visible=False)
                    step1_selected_class_name_hidden = gr.Textbox(visible=False)
                with gr.TabItem("⚙️ Device Configuration"):
                    gr.Markdown("### Edit Device Information")
                    gr.Markdown("Connect to a device. Current info will be loaded automatically. Modify as needed and save.")
                    step1_dev_model_gr = gr.Textbox(label="Device Model")
                    step1_dev_brand_gr = gr.Textbox(label="Device Brand")
                    step1_dev_system_version_gr = gr.Textbox(label="System Version (e.g., 12, 13)")
                    step1_dev_sdk_version_gr = gr.Textbox(label="SDK Version (e.g., 31, 33)")
                    step1_dev_font_scale_gr = gr.Textbox(label="Font Scale (e.g., 1.0, 1.15)")
                    step1_dev_dark_mode_gr = gr.Textbox(label="Dark Mode Enabled (true/false/unknown)")
                    step1_save_device_info_btn = gr.Button("💾 Save Device Information Changes")
                    step1_device_info_status_text_gr = gr.Textbox(label="Save Status", interactive=False, lines=1)
                with gr.TabItem("📝 Annotation & Save"):
                    gr.Markdown("### Annotate Selection and Save Record")
                    step1_user_notes_input = gr.Textbox(label="User Notes / Context", lines=3)
                    step1_target_label_input = gr.Textbox(label="Target Label (e.g., button_submit, text_username)", lines=1)
                    step1_selection_method_dropdown = gr.Dropdown(label="Selection Method", choices=["manual_tap", "ocr_tap", "programmatic", "not_applicable"], value="not_applicable")
                    with gr.Row():
                        step1_ocr_text_input = gr.Textbox(label="OCR Text (if applicable)", lines=2)
                        step1_corrected_text_input = gr.Textbox(label="Corrected Text (if applicable)", lines=2)
                    step1_save_btn = gr.Button("💾 Save Annotation Record")
                    step1_save_status_text = gr.Textbox(label="Save Status", interactive=False, lines=1)
                with gr.TabItem("📤 Export Data for Next Step"):
                    gr.Markdown("### Export Collected Data")
                    gr.Markdown("Click the button below to package all collected records, device configuration, and the last screenshot/XML into a ZIP file. This ZIP will be saved locally and its path will be displayed for use in Step 2.")
                    step1_export_all_data_btn = gr.Button("📦 Package and Export Data Locally")
                    step1_export_status_text = gr.Textbox(label="Export Status", interactive=False, lines=2)
            step1_connect_btn.click(fn=step1_app_instance.initialize_device,inputs=[step1_ip_port_input],outputs=[step1_status_text, step1_dev_model_gr, step1_dev_brand_gr, step1_dev_system_version_gr,step1_dev_sdk_version_gr, step1_dev_font_scale_gr, step1_dev_dark_mode_gr])
            step1_save_device_info_btn.click(fn=step1_app_instance.handle_save_device_info, inputs=[step1_dev_model_gr, step1_dev_brand_gr, step1_dev_system_version_gr, step1_dev_sdk_version_gr, step1_dev_font_scale_gr, step1_dev_dark_mode_gr], outputs=[step1_device_info_status_text_gr])
            step1_capture_btn.click(fn=step1_app_instance.capture_screenshot_and_xml, inputs=[], outputs=[step1_status_text, step1_img_annotated_display, step1_raw_img_url_hidden, step1_node_dropdown])
            step1_node_dropdown.select(fn=step1_app_instance.handle_node_selection, inputs=[step1_node_dropdown], outputs=[step1_status_text, step1_img_annotated_display, step1_element_details_display, step1_selected_bounds_hidden, step1_selected_xpath_hidden, step1_selected_resource_id_hidden, step1_selected_text_hidden, step1_selected_content_desc_hidden, step1_selected_class_name_hidden])
            step1_save_btn.click(fn=step1_app_instance.save_results, inputs=[step1_user_notes_input, step1_target_label_input, step1_selection_method_dropdown, step1_ocr_text_input, step1_corrected_text_input], outputs=[step1_save_status_text])
            async def handle_step1_export_wrapper(): path, status = await step1_app_instance.export_data_locally_for_handoff(); display_path_message = f"Output ZIP ready: {path}" if path else "Export failed. Check status."; return path, status, display_path_message
            step1_export_all_data_btn.click(fn=handle_step1_export_wrapper, inputs=[], outputs=[state_step1_output_zip_path, step1_export_status_text, step1_output_display_gr])

        with gr.TabItem("2. Data Cleaning & Filtering"):
            # ... (Existing Step 2 UI and logic - unchanged) ...
            gr.Markdown("## Tab 2: Dataset Cleaning and Filtering (from `step2_data_filter.py`)")
            step2_input_zip_path_display_gr = gr.Textbox(label="Input ZIP Path (from Step 1)", interactive=False)
            step2_load_from_step1_btn_gr = gr.Button("📂 Use Output from Step 1")
            gr.Markdown("--- OR ---")
            step2_manual_input_file_gr = gr.File(label="Alternatively, upload Dataset Manually (ZIP or PKL)", type="filepath")
            step2_output_filename_gr = gr.Textbox(label="Output Filename for Cleaned Data (PKL, inside `cleaned_datasets`)", value="cleaned_output.pkl")
            step2_run_button_gr = gr.Button("🧹 Run Cleaning and Save PKL", variant="primary")
            step2_status_display_gr = gr.Markdown("### Status & Results")
            async def handle_step2_cleaning(manual_file_upload_obj, path_from_step1_state_val, output_filename_str_val):
                status_messages_md = ""; output_pkl_path_for_state = None; display_message_for_accordion = "Step 2 not run or failed."
                actual_input_path = None; input_source_msg = ""
                if path_from_step1_state_val and Path(str(path_from_step1_state_val)).exists(): actual_input_path = str(path_from_step1_state_val); input_source_msg = f"Using input from Step 1: `{actual_input_path}`"
                elif manual_file_upload_obj: actual_input_path = manual_file_upload_obj.name; input_source_msg = f"Using manually uploaded file: `{Path(actual_input_path).name}`"
                else: status_messages_md = "Error: No input dataset provided. Either use output from Step 1 or upload a file."; return status_messages_md, None, "Step 2: Error - No input."
                status_messages_md += f"{input_source_msg}\n\n"
                if not output_filename_str_val.strip(): output_filename_str_val = f"cleaned_{Path(actual_input_path).stem}.pkl"
                elif not output_filename_str_val.endswith(".pkl"): output_filename_str_val = Path(output_filename_str_val).stem + ".pkl"
                output_file_path_obj = Path("cleaned_datasets") / Path(output_filename_str_val).name
                output_file_path_obj.parent.mkdir(parents=True, exist_ok=True)
                try:
                    status_messages_md += "Initializing dataset...\n"; dataset = DataSet(name=f"dataset_from_{Path(actual_input_path).stem}")
                    status_messages_md += f"Loading dataset from `{actual_input_path}`...\n"; dataset.load(actual_input_path)
                    if dataset.load_errors: errors_str = "<br>".join([f"&nbsp;&nbsp;- {err[0]}: {err[1][:100]}..." for err in dataset.load_errors[:5]]); status_messages_md += f"**Load errors encountered:**<br>{errors_str}\n"
                    if not dataset.records: status_messages_md += "**Warning: No records loaded. Aborting cleaning.**\n"; return status_messages_md, None, f"Step 2: Failed - No records in {Path(actual_input_path).name}"
                    status_messages_md += f"Successfully loaded {len(dataset.records)} records.\n"; status_messages_md += "Starting data cleaning and classification...\n"
                    cleaning_summary_dict = dataset.run(save_output=False)
                    summary_str = "<br>".join([f"&nbsp;&nbsp;- {k.replace('_', ' ').capitalize()}: {v}" for k,v in cleaning_summary_dict.items()]); status_messages_md += f"**Cleaning summary:**<br>{summary_str}\n"
                    status_messages_md += "Saving cleaned dataset...\n"; dataset.save(filepath=output_file_path_obj, save_type="pkl")
                    output_pkl_path_for_state = str(output_file_path_obj.resolve()); display_message_for_accordion = f"Cleaned PKL saved to: {output_pkl_path_for_state}"; status_messages_md += f"**Success!** {display_message_for_accordion}\n"
                except Exception as e: tb_str = traceback.format_exc(); status_messages_md += f"<br>**An error occurred during Step 2 processing:** {str(e)}\n"; status_messages_md += f"```\n{tb_str}\n```\n"; display_message_for_accordion = f"Step 2: Error - {str(e)}"
                return status_messages_md, output_pkl_path_for_state, display_message_for_accordion
            step2_load_from_step1_btn_gr.click(fn=lambda path_from_s1_state: path_from_s1_state if path_from_s1_state else "Error: Step 1 output not found or not valid.",inputs=[state_step1_output_zip_path],outputs=[step2_input_zip_path_display_gr])
            step2_run_button_gr.click(fn=handle_step2_cleaning,inputs=[step2_manual_input_file_gr, step2_input_zip_path_display_gr, step2_output_filename_gr],outputs=[step2_status_display_gr, state_step2_output_pkl_path, step2_output_display_gr])

        with gr.TabItem("3. Data Annotation (LLM-Assisted)"):
            gr.Markdown("## Tab 3: LLM-Assisted Annotation (from `step3_llm_4_annotated.py`)")
            
            step3_input_pkl_path_display_gr = gr.Textbox(label="Input PKL Path (from Step 2)", interactive=False)
            step3_load_from_step2_btn_gr = gr.Button("📂 Use Output from Step 2")
            
            gr.Markdown("--- OR ---")
            step3_dataset_file_input_manual_gr = gr.File(label="Alternatively, upload Dataset Manually (PKL or ZIP)", type="filepath")
            step3_existing_csv_input_gr = gr.File(label="Upload Existing Annotation CSV (Optional)", type="filepath")
            step3_load_dataset_button_gr = gr.Button("🚀 Load Dataset for Annotation")
            step3_status_text_load_gr = gr.Markdown("Status: Not loaded.")
            step3_output_csv_path_display_gr = gr.Textbox(label="Output CSV Path", interactive=False)

            with gr.Row():
                with gr.Column(scale=1): # Left column for controls and details
                    step3_current_record_text_gr = gr.Textbox(label="Current Record", interactive=False)
                    step3_ui_element_details_display_gr = gr.Textbox(label="UI Element Details (from Record)", lines=8, interactive=False)
                    
                    gr.Markdown("### Device Information")
                    with gr.Row():
                        step3_edit_device_info_button_gr = gr.Button("✏️ Edit", interactive=False)
                        step3_lock_device_info_button_gr = gr.Button("🔒 Lock", interactive=False)
                    step3_dev_model_gr = gr.Textbox(label="Model", interactive=False)
                    step3_dev_brand_gr = gr.Textbox(label="Brand", interactive=False)
                    # ... (all 8 device fields from step3_llm_4_annotated.py)
                    step3_dev_system_version_gr = gr.Textbox(label="System Version", interactive=False)
                    step3_dev_sdk_version_gr = gr.Textbox(label="SDK Version", interactive=False)
                    step3_dev_font_scale_gr = gr.Textbox(label="Font Scale", interactive=False)
                    step3_dev_dark_mode_gr = gr.Textbox(label="Dark Mode", interactive=False)
                    step3_dev_pkg_name_gr = gr.Textbox(label="Package Name", interactive=False)
                    step3_dev_app_category_gr = gr.Textbox(label="App Category", interactive=False)
                    
                    step3_device_info_textboxes_list = [
                        step3_dev_model_gr, step3_dev_brand_gr, step3_dev_system_version_gr, step3_dev_sdk_version_gr,
                        step3_dev_font_scale_gr, step3_dev_dark_mode_gr, step3_dev_pkg_name_gr, step3_dev_app_category_gr
                    ]
                    step3_device_info_buttons_list = [step3_edit_device_info_button_gr, step3_lock_device_info_button_gr]

                with gr.Column(scale=2): # Right column for image, LLM, and annotation
                    step3_screenshot_display_gr = gr.Image(label="Screenshot", type="filepath", visible=False, interactive=False)
                    gr.Markdown("### LLM Assistance & Final Annotation")
                    step3_system_prompt_input_gr = gr.Textbox(label="System Prompt for LLM", lines=3, value="You are a UI annotation assistant...")
                    step3_llm_answer_input_gr = gr.Textbox(label="LLM Suggested Answer", lines=3)
                    step3_user_annotation_final_input_gr = gr.Textbox(label="✅ Your Final Annotation Label", lines=2)
            
            with gr.Row():
                step3_prev_record_button_gr = gr.Button("⬅️ Previous Record")
                step3_next_record_button_gr = gr.Button("➡️ Next Record")
            step3_save_annotation_button_gr = gr.Button("💾 Save Annotation for This Record", variant="primary")
            step3_annotation_status_text_gr = gr.Textbox(label="Annotation Status", interactive=False)

            # --- Step 3 Core Logic Functions (Adapted from step3_llm_4_annotated.py) ---
            # These functions will operate on/update the gr.State variables
            
            # Adapted load_and_process_dataset_records
            def load_and_process_dataset_records_step3(dataset_file_obj_param, existing_csv_file_obj_param, pkl_path_from_step2_param):
                # This function now needs to return new state values and all UI updates
                # It will use the parameters instead of global variables from step3 script
                
                # Determine actual input path
                actual_input_path_str = None
                load_status_msg = ""
                if pkl_path_from_step2_param and Path(pkl_path_from_step2_param).exists():
                    actual_input_path_str = pkl_path_from_step2_param
                    load_status_msg = f"Using input from Step 2: `{actual_input_path_str}`\n"
                elif dataset_file_obj_param:
                    actual_input_path_str = dataset_file_obj_param.name
                    load_status_msg = f"Using manually uploaded file: `{Path(actual_input_path_str).name}`\n"
                else:
                    return [], -1, None, None, "Error: No dataset file provided.", *get_empty_state_step3() # Matches full output list
                
                input_path = Path(actual_input_path_str)
                new_loaded_dataset_path = input_path
                raw_records_list = []
                load_errors_list = []

                # ... (rest of the loading logic from step3_llm_4_annotated.py's load_and_process_dataset_records)
                # ... (ensure it uses local vars raw_records_list, load_errors_list)
                # ... (Example snippet of adaptation)
                if input_path.suffix == ".pkl":
                    with input_path.open('rb') as f:
                        loaded_data = pickle.load(f) # Using imported pickle
                        if isinstance(loaded_data, list) and all(isinstance(item, Record) for item in loaded_data): # Using imported Record
                            raw_records_list = loaded_data
                        else:
                            load_status_msg += "Error: PKL file does not contain a list of Record objects."
                            return [], -1, None, new_loaded_dataset_path, load_status_msg, *get_empty_state_step3()
                # ... (handle .zip similarly) ...
                elif input_path.suffix == ".zip":
                    # ... (zip loading logic adapted) ...
                    pass # Placeholder
                else:
                    load_status_msg += "Error: Unsupported dataset file type. Please use .pkl or .zip."
                    return [], -1, None, new_loaded_dataset_path, load_status_msg, *get_empty_state_step3()

                if not raw_records_list:
                    load_status_msg += "No records found in the dataset."
                    return [], -1, None, new_loaded_dataset_path, load_status_msg, *get_empty_state_step3()
                
                # Determine output CSV path
                new_output_csv_path = None
                if existing_csv_file_obj_param:
                    new_output_csv_path = Path(existing_csv_file_obj_param.name)
                    load_status_msg += f"Using existing CSV: {new_output_csv_path.name}\n"
                else:
                    timestamp_str = Path(input_path.stem).name
                    new_output_csv_path = Path("annotated_data") / f"annotations_{timestamp_str}.csv" # BASE_OUTPUT_DIR from step3
                    load_status_msg += f"New CSV will be: {new_output_csv_path.name}\n"
                new_output_csv_path.parent.mkdir(parents=True, exist_ok=True)

                processed_ui_records = []
                # ... (processing logic from step3_llm_4_annotated.py, populating processed_ui_records)
                # ... (using the record_identifier logic, etc.)
                for i, record_obj in enumerate(raw_records_list):
                    # Simplified processing for brevity in this example
                    dev_env = record_obj.device_and_app_environment.model_dump() if record_obj.device_and_app_environment else {}
                    img_url = str(record_obj.image_urls.raw_image_url) if record_obj.image_urls and record_obj.image_urls.raw_image_url else None
                    processed_ui_records.append({
                        "id": f"{dev_env.get('serial', 'unk')}_{record_obj.capture_timestamp if hasattr(record_obj, 'capture_timestamp') and record_obj.capture_timestamp else record_obj.session_id}",
                        "screenshot_url": img_url,
                        "ui_element_details": "Details...", # Placeholder
                        "device_env_data": dev_env,
                        "_original_record_obj": record_obj,
                        "_original_record_raw_json_dump": record_obj.model_dump(mode='json'),
                        "llm_prompt": "", "llm_answer": "", "user_annotation": ""
                    })


                new_current_idx = 0 if processed_ui_records else -1
                load_status_msg += f"Successfully processed {len(processed_ui_records)} records.\n"
                
                if processed_ui_records:
                    record_display_updates = get_display_for_record_step3(new_current_idx, processed_ui_records)
                    return processed_ui_records, new_current_idx, new_output_csv_path, new_loaded_dataset_path, load_status_msg, *record_display_updates, str(new_output_csv_path)
                else:
                    return [], -1, new_output_csv_path, new_loaded_dataset_path, load_status_msg, *get_empty_state_step3(), str(new_output_csv_path or "")

            # Adapted get_display_for_record
            def get_display_for_record_step3(record_idx_param, records_list_param):
                # ... (logic from step3_llm_4_annotated.py's get_display_for_record)
                # ... (Uses record_idx_param and records_list_param)
                # ... (Returns list of gr.update() for all step3_ UI elements)
                if not records_list_param or record_idx_param < 0 or record_idx_param >= len(records_list_param):
                    return get_empty_state_step3() # Call helper for empty/error state

                record_data = records_list_param[record_idx_param]
                dev_env = record_data.get("device_env_data", {})
                # This list MUST match the order of `all_step3_ui_outputs_for_nav_load`
                return [
                    gr.update(value=record_data.get("screenshot_url"), visible=bool(record_data.get("screenshot_url"))),
                    gr.update(value=record_data.get("ui_element_details", "")),
                    gr.update(value=f"Record {record_idx_param + 1} of {len(records_list_param)} (ID: {record_data.get('id')})"),
                    gr.update(value=record_data.get("llm_prompt", "")),
                    gr.update(value=record_data.get("llm_answer", "")),
                    gr.update(value=""), # annotation_status_text
                    gr.update(value=dev_env.get('model', ''), interactive=False),
                    gr.update(value=dev_env.get('brand', ''), interactive=False),
                    gr.update(value=dev_env.get('system_version', ''), interactive=False),
                    gr.update(value=dev_env.get('sdk_version', ''), interactive=False),
                    gr.update(value=str(dev_env.get('font_scale', 'N/A')), interactive=False),
                    gr.update(value=str(dev_env.get('dark_mode_enabled', 'unknown')), interactive=False),
                    gr.update(value=dev_env.get('package_name', ''), interactive=False),
                    gr.update(value=dev_env.get('app_category', ''), interactive=False),
                    gr.update(interactive=True), # edit button
                    gr.update(interactive=False) # lock button
                ]
            
            def get_empty_state_step3(): # Helper for empty/error UI state
                num_main_outputs = 6; num_device_outputs = 8; num_device_buttons = 2
                empty_state = [gr.update(value="", interactive=False)] * (num_main_outputs + num_device_outputs + num_device_buttons)
                empty_state[0] = gr.update(value=None, visible=False, interactive=False) # screenshot
                empty_state[num_main_outputs + num_device_outputs] = gr.update(interactive=False) # edit button
                empty_state[num_main_outputs + num_device_outputs + 1] = gr.update(interactive=False) # lock button
                return empty_state

            # Adapted navigation
            def handle_nav_step3(direction, current_idx_param, records_list_param):
                new_idx = current_idx_param
                if direction == "prev": new_idx = max(0, current_idx_param - 1)
                else: new_idx = min(len(records_list_param) - 1, current_idx_param + 1)
                
                if not records_list_param: return -1, *get_empty_state_step3()
                return new_idx, *get_display_for_record_step3(new_idx, records_list_param)

            # Adapted toggle_device_info_edit_mode
            def toggle_device_info_edit_mode_step3(is_editable_param):
                updates = [gr.update(interactive=is_editable_param)] * 8 # 8 device textboxes
                updates.append(gr.update(interactive=not is_editable_param)) # Edit button
                updates.append(gr.update(interactive=is_editable_param))   # Lock button
                return updates
            
            # Adapted collect_and_save_annotation
            def collect_and_save_annotation_step3(current_idx_param, records_list_param, output_csv_path_param, llm_prompt_ui, llm_answer_ui, user_anno_ui, *device_info_ui_list):
                if current_idx_param < 0 or current_idx_param >= len(records_list_param):
                    return records_list_param, "Error: No valid record selected." # Return original list and error
                
                # Unpack device_info_ui_list
                dev_model, dev_brand, dev_sys, dev_sdk, dev_font, dev_dark, dev_pkg, dev_cat = device_info_ui_list
                
                # Call adapted save_annotation_step3
                updated_records_list, status_msg = save_annotation_step3(
                    current_idx_param, records_list_param, output_csv_path_param,
                    llm_prompt_ui, llm_answer_ui, user_anno_ui,
                    dev_model, dev_brand, dev_sys, dev_sdk, dev_font, dev_dark, dev_pkg, dev_cat
                )
                return updated_records_list, status_msg

            # Adapted save_annotation
            def save_annotation_step3(record_idx, records_list, csv_path, llm_prompt, llm_answer, user_annotation, *dev_infos):
                # ... (logic from step3_llm_4_annotated.py's save_annotation)
                # ... (Uses parameters, updates records_list[record_idx], saves to csv_path)
                # ... (Returns updated records_list and status message)
                if not csv_path: return records_list, "Error: Output CSV path not set."
                current_record_data = records_list[record_idx]
                original_dev_env = current_record_data.get("device_env_data", {})
                updated_dev_env = original_dev_env.copy()
                
                # Update with UI values (dev_infos order must match UI list)
                keys = ['model', 'brand', 'system_version', 'sdk_version', 'font_scale', 'dark_mode_enabled', 'package_name', 'app_category']
                for i, key in enumerate(keys):
                    if key == 'font_scale': 
                        try: updated_dev_env[key] = float(dev_infos[i])
                        except ValueError: updated_dev_env[key] = dev_infos[i]
                    else: updated_dev_env[key] = dev_infos[i]
                
                try:
                    dev_env_obj = DeviceAndAppEnvironment(**updated_dev_env)
                    dev_env_json = dev_env_obj.model_dump_json()
                    records_list[record_idx]['device_env_data'] = dev_env_obj.model_dump() # Update in-memory
                except Exception as e: return records_list, f"Error validating device info: {e}"

                original_record_obj = current_record_data.get("_original_record_obj")
                img_urls_json = original_record_obj.image_urls.model_dump_json() if original_record_obj and original_record_obj.image_urls else "{}"
                sel_details_json = original_record_obj.selection_details.model_dump_json() if original_record_obj and original_record_obj.selection_details else "{}"

                output_data_dict = {
                    "record_id": current_record_data.get("id"), "image_urls_json": img_urls_json,
                    "selection_details_json": sel_details_json, "device_and_app_environment_json": dev_env_json,
                    "llm_prompt": llm_prompt, "llm_answer": llm_answer, "user_annotation_final": user_annotation,
                    "full_original_record_json": json.dumps(current_record_data.get("_original_record_raw_json_dump", {})),
                    "annotation_timestamp": pd.Timestamp.now().isoformat()
                }
                # Update in-memory records_list for other fields
                records_list[record_idx]["llm_prompt"] = llm_prompt
                records_list[record_idx]["llm_answer"] = llm_answer
                records_list[record_idx]["user_annotation"] = user_annotation

                df_new = pd.DataFrame([output_data_dict])
                if Path(csv_path).exists():
                    df_old = pd.read_csv(csv_path)
                    df_old = df_old[df_old['record_id'] != output_data_dict['record_id']]
                    df_to_save = pd.concat([df_old, df_new], ignore_index=True)
                else: df_to_save = df_new
                df_to_save.to_csv(csv_path, index=False)
                return records_list, f"Annotation for {output_data_dict['record_id']} saved."

            # --- Step 3 Event Handlers ---
            step3_all_ui_outputs_for_nav_load = [
                step3_screenshot_display_gr, step3_ui_element_details_display_gr, step3_current_record_text_gr,
                step3_system_prompt_input_gr, step3_llm_answer_input_gr, step3_annotation_status_text_gr
            ] + step3_device_info_textboxes_list + step3_device_info_buttons_list

            step3_load_from_step2_btn_gr.click(
                fn=lambda path_from_s2: path_from_s2 if path_from_s2 else "Error: Step 2 output not found.",
                inputs=[state_step2_output_pkl_path],
                outputs=[step3_input_pkl_path_display_gr]
            )

            step3_load_dataset_button_gr.click(
                fn=load_and_process_dataset_records_step3,
                inputs=[step3_dataset_file_input_manual_gr, step3_existing_csv_input_gr, step3_input_pkl_path_display_gr], # Added pkl_path_from_step2_display
                outputs=[
                    state_step3_ui_records, state_step3_current_index, state_step3_output_csv_path, 
                    gr.State(None), # For new_loaded_dataset_path (not directly used in UI here)
                    step3_status_text_load_gr
                ] + step3_all_ui_outputs_for_nav_load + [step3_output_csv_path_display_gr] # Unpack UI updates
            )
            
            step3_prev_record_button_gr.click(
                fn=lambda current_idx, records_list: handle_nav_step3("prev", current_idx, records_list),
                inputs=[state_step3_current_index, state_step3_ui_records],
                outputs=[state_step3_current_index] + step3_all_ui_outputs_for_nav_load
            )
            step3_next_record_button_gr.click(
                fn=lambda current_idx, records_list: handle_nav_step3("next", current_idx, records_list),
                inputs=[state_step3_current_index, state_step3_ui_records],
                outputs=[state_step3_current_index] + step3_all_ui_outputs_for_nav_load
            )

            step3_edit_device_info_button_gr.click(
                fn=lambda: toggle_device_info_edit_mode_step3(True),
                inputs=None, outputs=step3_device_info_textboxes_list + step3_device_info_buttons_list
            )
            step3_lock_device_info_button_gr.click(
                fn=lambda: toggle_device_info_edit_mode_step3(False),
                inputs=None, outputs=step3_device_info_textboxes_list + step3_device_info_buttons_list
            )

            step3_save_annotation_button_gr.click(
                fn=collect_and_save_annotation_step3,
                inputs=[
                    state_step3_current_index, state_step3_ui_records, state_step3_output_csv_path,
                    step3_system_prompt_input_gr, step3_llm_answer_input_gr, step3_user_annotation_final_input_gr
                ] + step3_device_info_textboxes_list,
                outputs=[state_step3_ui_records, step3_annotation_status_text_gr] # Update records list and status
            )

if __name__ == '__main__':
    print("Launching Main Gradio Application...")
    main_app_ui.launch(debug=True, share=False)
