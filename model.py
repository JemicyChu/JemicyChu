from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, HttpUrl, field_validator
import json

class ImageUrls(BaseModel):
    raw_image_url: Optional[HttpUrl] = None
    image_height: Optional[int] = None
    image_width: Optional[int] = None

class NodeData(BaseModel):
    resource_id: Optional[str] = Field(None, serialization_alias='resource-id')
    text: Optional[str] = None
    description: Optional[str] = Field(None, serialization_alias='content-desc')
    class_name: Optional[str] = Field(None, serialization_alias='class')
    package_name: Optional[str] = Field(None, serialization_alias='package')
    x_path: Optional[str] = None
    # Raw attributes from UiAutomator2, stored as a JSON string or dict
    raw_attributes: Optional[Union[str, Dict[str, Any]]] = None

    @field_validator('raw_attributes')
    def ensure_json_string(cls, value):
        if isinstance(value, dict):
            return json.dumps(value)
        return value

class SelectionDetails(BaseModel):
    image_evidence: Optional[ImageUrls] = None
    node_data: Optional[NodeData] = None
    ocr_text: Optional[str] = None
    corrected_text: Optional[str] = None
    selection_method: Optional[str] = None
    is_visible: Optional[bool] = None
    screen_bounds: Optional[str] = None # Example: "[0,0][1080,2280]"
    element_bounds: Optional[str] = None # Example: "[44,1322][1036,1390]"
    context_from_source_app: Optional[str] = None
    is_top_level_target: Optional[bool] = True

class DeviceAndAppEnvironment(BaseModel):
    # --- Fields primarily captured during initial device connection (step1_data_store.py) ---
    model: Optional[str] = None                 # Device model
    brand: Optional[str] = None                 # Device brand
    serial: Optional[str] = None                # Device serial number
    system_version: Optional[str] = None        # Android OS version (e.g., "12", "N/A")
    sdk_version: Optional[str] = None           # Android SDK API level as string (e.g., "31", "N/A")

    # --- Fields captured initially and potentially confirmed/edited at save/annotation ---
    font_scale: Optional[Union[float, str]] = None # System font scale (e.g., 1.0, 1.15, "N/A", "unknown")
    dark_mode_enabled: Optional[str] = None     # Dark mode status (e.g., "true", "false", "unknown (2)")

    # --- Fields related to the application state at capture time (step1_data_store.py) ---
    package_name: Optional[str] = None          # Package name of the foreground app
    activity: Optional[str] = None              # Activity name of the foreground app
    app_name: Optional[str] = None              # User-facing name of the app (often N/A or requires extra effort)
    app_category: Optional[str] = None          # User-defined category for the app (e.g., "System App", "Social Media")

    # --- Fields captured at the moment of saving data (step1_data_store.py, save_results) ---
    font_scale_at_save: Optional[Union[float, str]] = None # Font scale at the time of saving
    dark_mode_enabled_at_save: Optional[str] = None    # Dark mode status at the time of saving

    # --- Additional device properties from uiautomator2 device.info (potentially at save time) ---
    currentPackageName: Optional[str] = None    # Current foreground package name (often same as package_name)
    displayHeight: Optional[int] = None         # Display height in pixels
    displayWidth: Optional[int] = None          # Display width in pixels
    displayRotation: Optional[int] = None       # Current display rotation (0, 1, 2, 3)
    displaySizeDpX: Optional[int] = None        # Display width in DP
    displaySizeDpY: Optional[int] = None        # Display height in DP
    productName: Optional[str] = None           # Product name
    screenOn: Optional[bool] = None             # True if screen is on
    sdkInt: Optional[int] = None                # SDK API level as integer (e.g., 31) - consistency with sdk_version (string) is handled by data source
    naturalOrientation: Optional[bool] = None   # True if current orientation is natural orientation

class Record(BaseModel):
    session_id: str
    selection_details: Optional[SelectionDetails] = None
    device_and_app_environment: Optional[DeviceAndAppEnvironment] = None
    # Allow any other fields
    class Config:
        extra = "allow"
