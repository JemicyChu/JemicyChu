import aiohttp
import ujson
import pprint
import os
import aiofiles
from typing import Union, Optional # Make sure Optional is also imported for type hinting file_bytes

async def upload_file(filename: str, file_source: Union[str, bytes]):
    url = 'http://10.101.32.184:10010/upload'
    params = {
        'output': 'json',
        'path': '/',
        'scene': '',
        'code': '',
        'auth_token': '',
    }

    file_bytes: Optional[bytes] = None # Added Optional for type hinting

    if isinstance(file_source, bytes):
        file_bytes = file_source
    elif isinstance(file_source, str):
        if file_source.startswith(('http://', 'https://')):
            try:
                async with aiohttp.ClientSession() as session: # Ensure ClientSession is called
                    async with session.get(file_source) as response:
                        if response.status == 200:
                            file_bytes = await response.read()
                        else:
                            pprint.pprint(f"Failed to download file from URL: {file_source}. Status: {response.status}")
                            return None
            except Exception as e:
                pprint.pprint(f"Error downloading file from URL: {file_source}. Error: {e}")
                return None
        elif os.path.exists(file_source): # Check if it's a local path
            try:
                async with aiofiles.open(file_source, 'rb') as f:
                    file_bytes = await f.read()
            except Exception as e:
                pprint.pprint(f"Error reading local file: {file_source}. Error: {e}")
                return None
        else:
            pprint.pprint(f"File source string is not a valid URL or existing local file path: {file_source}")
            return None
    else:
        pprint.pprint(f"Unsupported file_source type: {type(file_source)}")
        return None

    if file_bytes is None:
        pprint.pprint(f"Could not obtain file bytes for {filename}")
        return None

    data = aiohttp.FormData()
    data.add_field('file', file_bytes, filename=filename, content_type='multipart/form-data')

    try:
        async with aiohttp.ClientSession() as session: # Ensure ClientSession is called
            async with session.post(url, params=params, data=data) as response:
                if response.status == 200:
                    response_text = await response.text()
                    json_response = ujson.loads(response_text)
                    return json_response['url']
                else:
                    pprint.pprint(f"Upload failed. Status code: {response.status}. Response: {await response.text()}")
                    return None
    except Exception as e:
        pprint.pprint(f'Upload file error: {e}')
        return None
