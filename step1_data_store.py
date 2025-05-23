import gradio as gr
import logging
import json
from datetime import datetime
import pprint
import os # Added os for os.path.join if needed, though not explicitly in target for this step
from model import Record, SelectionDetails, DeviceAndAppEnvironment, NodeData, ImageUrls # Assuming model.py is in the same directory or accessible
from AndroidDevice import AndroidPage, upload_file # Assuming AndroidDevice.py is accessible

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AndroidGradioApp:
    def __init__(self):
        self.android_device = None
        self.ui_elements_cache = {}
        self.current_screenshot_path = None
        self.current_xml_path = None
        self.raw_image_url = None
        self.processed_image_url = None
        self.device_config_info = {} # Will store model, brand, system_version etc.
        self.current_selection_details = SelectionDetails() # Initialize with default or empty

    async def initialize_device(self, ip_port_str):
        logging.info(f"Attempting to connect to device: {ip_port_str}")
        num_device_config_fields = 6 # model, brand, system_version, sdk_version, font_scale, dark_mode_enabled
        error_return_values_default = [""] * num_device_config_fields

        try:
            self.android_device = AndroidPage(ip_port_str)
            if self.android_device.device_is_connected():
                device_info = await self.android_device.get_device_info() # This is a dict
                
                self.device_config_info = {
                    "model": device_info.get("model", "N/A"),
                    "brand": device_info.get("brand", "N/A"),
                    "system_version": device_info.get("version", device_info.get("release", "N/A")),
                    "sdk_version": str(device_info.get("sdk", "N/A")),
                    "serial": device_info.get("serial", "N/A"),
                    "font_scale": "N/A", 
                    "dark_mode_enabled": "unknown"
                }
                self.device_config_info.update(device_info) # Merge all fields from device_info

                try:
                    font_scale_val = await self.android_device.get_font_scale()
                    self.device_config_info["font_scale"] = str(font_scale_val) if font_scale_val is not None else "N/A"
                except Exception as e:
                    logging.warning(f"Could not fetch font scale: {e}")
                    self.device_config_info["font_scale"] = "Error fetching"

                try:
                    dark_mode_val = await self.android_device.is_dark_mode_enabled()
                    self.device_config_info["dark_mode_enabled"] = str(dark_mode_val).lower() if dark_mode_val is not None else "unknown"
                except Exception as e:
                    logging.warning(f"Could not fetch dark mode status: {e}")
                    self.device_config_info["dark_mode_enabled"] = "Error fetching"

                device_summary = (
                    f"Model: {self.device_config_info.get('model', 'N/A')}, "
                    f"Brand: {self.device_config_info.get('brand', 'N/A')}, "
                    f"OS: {self.device_config_info.get('system_version', 'N/A')}, "
                    f"SDK: {self.device_config_info.get('sdk_version', 'N/A')}"
                )
                status = f"Device connected. Info: {device_summary}"
                logging.info(status)
                return [status] + self.get_device_info_for_ui()
            else:
                logging.error("Device connection failed: AndroidPage reported not connected.")
                return ["Failed to connect. Check IP/Serial and ADB."] + error_return_values_default
        except Exception as e:
            logging.error(f"Error initializing device: {e}", exc_info=True)
            return [f"Error: {str(e)}"] + [gr.update(value="Error")] * num_device_config_fields

    def get_device_info_for_ui(self):
        # Returns current device info values for UI textboxes
        # Order must match the new Gradio textboxes for device config
        return [
            str(self.device_config_info.get('model', '')),
            str(self.device_config_info.get('brand', '')),
            str(self.device_config_info.get('system_version', '')),
            str(self.device_config_info.get('sdk_version', '')),
            str(self.device_config_info.get('font_scale', '')),
            str(self.device_config_info.get('dark_mode_enabled', ''))
        ]

    async def handle_save_device_info(self, model, brand, system_version, sdk_version, font_scale_str, dark_mode_enabled_str):
        if not self.android_device or not self.device_config_info:
            logging.warning("Attempted to save device info, but device not connected or initial info not loaded.")
            return "Error: Device not connected or initial info not loaded. Connect first."

        self.device_config_info['model'] = model
        self.device_config_info['brand'] = brand
        self.device_config_info['system_version'] = system_version
        self.device_config_info['sdk_version'] = sdk_version
        self.device_config_info['font_scale'] = font_scale_str
        self.device_config_info['dark_mode_enabled'] = dark_mode_enabled_str.lower() # Normalize to lower

        # Ensure other parts of the system that use device_config_info see consistent keys if they rely on older names
        self.device_config_info['version'] = system_version 
        self.device_config_info['sdk'] = sdk_version

        logging.info(f"Device info updated by user: {pprint.pformat(self.device_config_info)}")
        return "Device information updated successfully."

    async def capture_screenshot_and_xml(self):
        if not self.android_device or not self.android_device.device_is_connected():
            logging.warning("Device not connected. Cannot capture.")
            return "Error: Device not connected.", None, None, None
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_screenshot_path, self.current_xml_path, hierarchy_json = await self.android_device.capture_layout(f"capture_{timestamp}")
            
            # Upload screenshot and get URL
            if self.current_screenshot_path:
                self.raw_image_url = await upload_file(os.path.basename(self.current_screenshot_path), self.current_screenshot_path)
                if not self.raw_image_url:
                    logging.error("Failed to upload raw screenshot.")
            
            # For now, processed_image_url is the same as raw_image_url
            self.processed_image_url = self.raw_image_url

            # Populate dropdown
            node_options = []
            if hierarchy_json:
                for node_dict in hierarchy_json:
                    text = node_dict.get('text', '')
                    desc = node_dict.get('description', '')
                    node_id = node_dict.get('resource_id', 'N/A')
                    display_text = f"ID: {node_id}, Text: '{text}', Desc: '{desc}'"
                    node_options.append((display_text, json.dumps(node_dict))) # Store full dict as value

            self.ui_elements_cache = hierarchy_json # Store for later use
            
            status_message = f"Screenshot and XML captured. Raw URL: {self.raw_image_url}"
            logging.info(status_message)
            
            # Return processed URL for display, raw URL for data, and node options
            return status_message, self.processed_image_url, self.raw_image_url, gr.update(choices=node_options, value=None)

        except Exception as e:
            logging.error(f"Error capturing screenshot/XML: {e}", exc_info=True)
            return f"Error: {str(e)}", None, None, gr.update(choices=[], value=None)

    async def handle_node_selection(self, selected_node_json_str):
        if not selected_node_json_str:
            return "No node selected.", None, None, None, None, None, None, None, None
        try:
            selected_node_dict = json.loads(selected_node_json_str)
            
            # Create NodeData Pydantic model
            node_data = NodeData(
                resource_id=selected_node_dict.get('resource_id'),
                text=selected_node_dict.get('text'),
                description=selected_node_dict.get('description'), # content-desc
                class_name=selected_node_dict.get('class_name'),   # class
                package_name=selected_node_dict.get('package_name'), # package
                x_path=selected_node_dict.get('xpath'),
                raw_attributes=selected_node_dict # Store all attributes
            )
            
            # Create ImageUrls Pydantic model
            image_urls = ImageUrls(
                raw_image_url=self.raw_image_url, # From capture step
                # Assuming image_height and image_width might be derived or N/A for now
            )

            # Update current_selection_details
            self.current_selection_details = SelectionDetails(
                image_evidence=image_urls,
                node_data=node_data,
                # ocr_text, corrected_text, selection_method etc. can be updated if UI for them exists
                is_visible=selected_node_dict.get('visible-to-user'),
                screen_bounds=selected_node_dict.get('bounds_on_screen'), # Example string "[0,0][1080,2280]"
                element_bounds=selected_node_dict.get('bounds_in_parent'), # Example string "[44,1322][1036,1390]"
            )
            
            # For UI display, extract some fields
            bounds_str = selected_node_dict.get('bounds_on_screen', "N/A")
            xpath_str = selected_node_dict.get('xpath', "N/A")
            
            # Prepare detailed text for the UI
            details_text = (
                f"Selected Element Details:\n"
                f"Resource ID: {node_data.resource_id or 'N/A'}\n"
                f"Text: {node_data.text or 'N/A'}\n"
                f"Content Description: {node_data.description or 'N/A'}\n"
                f"Class Name: {node_data.class_name or 'N/A'}\n"
                f"Package Name: {node_data.package_name or 'N/A'}\n"
                f"Bounds: {bounds_str}\n"
                f"XPath: {xpath_str}\n"
                # Add more fields as needed
            )
            
            # Draw bounding box if bounds are available
            # This part would call a drawing utility if bounds_str is valid
            # For now, we just pass the URL and bounds; actual drawing happens client-side or via another service
            # Or, if drawing on server: self.processed_image_url = await self.android_device.draw_box_on_image(self.current_screenshot_path, bounds_str, "output_annotated.png")

            logging.info(f"Node selected: {node_data.resource_id or node_data.text}")
            return "Node selected.", self.processed_image_url, details_text, bounds_str, xpath_str, node_data.resource_id, node_data.text, node_data.description, node_data.class_name

        except Exception as e:
            logging.error(f"Error handling node selection: {e}", exc_info=True)
            return f"Error: {str(e)}", self.raw_image_url, "Error processing selection.", None, None, None, None, None, None

    async def save_results(self, user_notes, target_label, selection_method, ocr_text, corrected_text):
        if not self.android_device or not self.current_screenshot_path:
            logging.warning("Cannot save, device not connected or no screenshot taken.")
            return "Error: Device not connected or no data to save."
        try:
            # Update SelectionDetails with manually entered/confirmed data
            if self.current_selection_details:
                self.current_selection_details.ocr_text = ocr_text
                self.current_selection_details.corrected_text = corrected_text
                self.current_selection_details.selection_method = selection_method
                self.current_selection_details.context_from_source_app = user_notes # User notes used as context

            # Create DeviceAndAppEnvironment Pydantic model using self.device_config_info
            # Ensure all fields from model.py are covered, using N/A or None if not available
            device_env = DeviceAndAppEnvironment(
                model=self.device_config_info.get('model'),
                brand=self.device_config_info.get('brand'),
                serial=self.device_config_info.get('serial'),
                system_version=str(self.device_config_info.get('system_version', self.device_config_info.get('version'))), # From model.py, this is str
                sdk_version=str(self.device_config_info.get('sdk_version', self.device_config_info.get('sdk'))), # From model.py, this is str
                font_scale=str(self.device_config_info.get('font_scale', "N/A")), # From model.py, Union[float, str]
                dark_mode_enabled=str(self.device_config_info.get('dark_mode_enabled', "unknown")).lower(), # From model.py, str

                package_name=self.device_config_info.get('currentPackageName'), # Assuming this is available
                activity=self.device_config_info.get('currentActivity'), # Assuming this is available
                app_name=self.device_config_info.get('appName', "N/A"), # Often N/A
                app_category=self.device_config_info.get('appCategory', "Unknown"), # User-defined or default

                font_scale_at_save=str(await self.android_device.get_font_scale() if self.android_device else self.device_config_info.get('font_scale')),
                dark_mode_enabled_at_save=str(await self.android_device.is_dark_mode_enabled() if self.android_device else self.device_config_info.get('dark_mode_enabled')).lower(),
                
                # Fields from device.info (uiautomator2)
                currentPackageName=self.device_config_info.get('currentPackageName'),
                displayHeight=self.device_config_info.get('displayHeight'),
                displayWidth=self.device_config_info.get('displayWidth'),
                displayRotation=self.device_config_info.get('displayRotation'),
                displaySizeDpX=self.device_config_info.get('displaySizeDpX'),
                displaySizeDpY=self.device_config_info.get('displaySizeDpY'),
                productName=self.device_config_info.get('productName'),
                screenOn=self.device_config_info.get('screenOn'),
                sdkInt=self.device_config_info.get('sdkInt', self.device_config_info.get('sdk')), # Integer version of SDK
                naturalOrientation=self.device_config_info.get('naturalOrientation')
            )
            
            # Create Record Pydantic model
            record = Record(
                session_id=f"session_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                selection_details=self.current_selection_details,
                device_and_app_environment=device_env,
                # Add other fields to Record as needed, e.g., target_label, user_notes
                user_notes=user_notes,
                target_label=target_label
            )
            
            # Save to JSON file
            output_dir = "collected_data"
            os.makedirs(output_dir, exist_ok=True)
            filename = os.path.join(output_dir, f"record_{record.session_id}.json")
            
            with open(filename, 'w') as f:
                json.dump(record.model_dump(mode='json'), f, indent=4) # Use model_dump for Pydantic v2
            
            logging.info(f"Data saved to {filename}")
            return f"Data saved successfully to {filename}"

        except Exception as e:
            logging.error(f"Error saving results: {e}", exc_info=True)
            # Use pprint to format the exception object for more detailed logging
            pprint.pprint(f"Exception details: {e}")
            return f"Error saving data: {str(e)}"

app_instance = AndroidGradioApp()

# Global wrapper for connect click
async def handle_connect_click(ip_port_str):
    # This will be modified to return a list
    return await app_instance.initialize_device(ip_port_str)

async def handle_capture_click():
    return await app_instance.capture_screenshot_and_xml()

async def handle_node_select_change(evt: gr.SelectData):
    if evt.value: # evt.value is the json string for the node
      return await app_instance.handle_node_selection(evt.value)
    return "No node selected or event data missing.", None, "No details.", None, None, None, None, None, None


async def handle_save_click(user_notes, target_label, selection_method, ocr_text, corrected_text):
    return await app_instance.save_results(user_notes, target_label, selection_method, ocr_text, corrected_text)

# Gradio UI Layout
with gr.Blocks() as demo:
    gr.Markdown("# Android UI Data Collector")
    
    # Status text for general messages
    status_text = gr.Textbox(label="Status", interactive=False, lines=1, value="Connect to device to begin.")

    with gr.Tabs():
        with gr.TabItem("📱 Device Connection & Capture"):
            with gr.Row():
                ip_port_input = gr.Textbox(label="Device IP:Port (e.g., 192.168.1.100:7912 or ADB serial)", value="127.0.0.1:5555")
                connect_btn = gr.Button("🔌 Connect to Device")
            
            capture_btn = gr.Button("📸 Capture Screenshot & UI XML")
            
            with gr.Row():
                img_annotated_display = gr.Image(label="Current Screen (Annotated)", type="filepath", interactive=False)
                raw_img_url_hidden = gr.Textbox(label="Raw Image URL", visible=False) 
            
            gr.Markdown("### Select UI Element from Hierarchy")
            node_dropdown = gr.Dropdown(label="Select UI Element", choices=[], interactive=True)
            element_details_display = gr.Textbox(label="Selected Element Details", lines=10, interactive=False)

            selected_bounds_hidden = gr.Textbox(visible=False)
            selected_xpath_hidden = gr.Textbox(visible=False)
            selected_resource_id_hidden = gr.Textbox(visible=False)
            selected_text_hidden = gr.Textbox(visible=False)
            selected_content_desc_hidden = gr.Textbox(visible=False)
            selected_class_name_hidden = gr.Textbox(visible=False)

        with gr.TabItem("⚙️ Device Configuration") as device_config_tab:
            gr.Markdown("### Edit Device Information")
            gr.Markdown("Connect to a device. Current info will be loaded automatically. Modify as needed and save.")
            
            device_model_gr = gr.Textbox(label="Device Model")
            device_brand_gr = gr.Textbox(label="Device Brand")
            device_system_version_gr = gr.Textbox(label="System Version (e.g., 12, 13)")
            device_sdk_version_gr = gr.Textbox(label="SDK Version (e.g., 31, 33)")
            device_font_scale_gr = gr.Textbox(label="Font Scale (e.g., 1.0, 1.15)")
            device_dark_mode_gr = gr.Textbox(label="Dark Mode Enabled (true/false/unknown)")

            save_device_info_btn = gr.Button("💾 Save Device Information Changes")
            device_info_status_text_gr = gr.Textbox(label="Save Status", interactive=False, lines=1)

        with gr.TabItem("📝 Annotation & Save"):
            gr.Markdown("### Annotate Selection and Save Record")
            user_notes_input = gr.Textbox(label="User Notes / Context", lines=3)
            target_label_input = gr.Textbox(label="Target Label (e.g., button_submit, text_username)", lines=1)
            selection_method_dropdown = gr.Dropdown(label="Selection Method", choices=["manual_tap", "ocr_tap", "programmatic", "not_applicable"], value="not_applicable")
            
            with gr.Row():
                ocr_text_input = gr.Textbox(label="OCR Text (if applicable)", lines=2)
                corrected_text_input = gr.Textbox(label="Corrected Text (if applicable)", lines=2)
            
            save_btn = gr.Button("💾 Save Annotation Record")
            save_status_text = gr.Textbox(label="Save Status", interactive=False, lines=1)

    # Event Handlers
    # Event Handlers
    connect_btn.click(
        handle_connect_click, # Global wrapper
        inputs=[ip_port_input],
        outputs=[
            status_text, 
            device_model_gr, device_brand_gr, device_system_version_gr,
            device_sdk_version_gr, device_font_scale_gr, device_dark_mode_gr
        ]
    )

    save_device_info_btn.click(
        app_instance.handle_save_device_info,
        inputs=[
            device_model_gr, device_brand_gr, device_system_version_gr,
            device_sdk_version_gr, device_font_scale_gr, device_dark_mode_gr
        ],
        outputs=[device_info_status_text_gr]
    )

    capture_btn.click(
        handle_capture_click,
        inputs=[],
        outputs=[status_text, img_annotated_display, raw_img_url_hidden, node_dropdown]
    )

    node_dropdown.select( # Use .select event for gr.Dropdown
        handle_node_select_change,
        inputs=[], # No direct inputs, event data is used
        outputs=[
            status_text, img_annotated_display, element_details_display,
            selected_bounds_hidden, selected_xpath_hidden, selected_resource_id_hidden,
            selected_text_hidden, selected_content_desc_hidden, selected_class_name_hidden
        ]
    )
    
    save_btn.click(
        handle_save_click,
        inputs=[user_notes_input, target_label_input, selection_method_dropdown, ocr_text_input, corrected_text_input],
        outputs=[save_status_text]
    )

if __name__ == "__main__":
    demo.launch(share=False)
