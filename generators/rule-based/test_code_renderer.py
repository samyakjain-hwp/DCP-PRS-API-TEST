import json
import copy
from typing import List, Dict, Any
from models import ApiSpec, TestCase

class TestCodeRenderer:
    def render(self, spec: ApiSpec, test_cases: List[TestCase]) -> str:
        sb = []
        sb.append("import pytest")
        sb.append("import requests")
        needs_random = any(getattr(tc, 'useRandomTestData', False) for tc in test_cases)
        if needs_random:
            sb.append("import random")
        sb.append("import base64")
        sb.append("import os")
        sb.append("import io")
        sb.append("import json")
        sb.append("from dotenv import load_dotenv")
        sb.append("")
        sb.append("load_dotenv()")
        sb.append("")
        
        has_credentials = bool(spec.username and spec.password)
        is_bearer_auth = spec.authType == "BEARER"
        needs_auth = has_credentials or is_bearer_auth
        
        sb.append(f"BASE_URL = os.getenv('TEST_BASE_URL', '{spec.baseUrl}')")
        if needs_auth:
            sb.append("TEST_USERNAME = os.getenv('TEST_USERNAME', '')")
            sb.append("TEST_PASSWORD = os.getenv('TEST_PASSWORD', '')")
        sb.append("")
        
        # Pytest fixture for auth
        if needs_auth:
            sb.append("@pytest.fixture(scope='module')")
            sb.append("def authorization():")
            sb.append("    credentials = f'{TEST_USERNAME}:{TEST_PASSWORD}'")
            sb.append("    basic_auth = 'Basic ' + base64.b64encode(credentials.encode()).decode()")
            if is_bearer_auth:
                sb.append("    # Login to get JWT")
                sb.append("    url = f'{BASE_URL}/v1/auth/login'")
                sb.append("    headers = {'content-type': 'application/json', 'accept': 'application/json'}")
                sb.append("    payload = {'authorization': basic_auth}")
                sb.append("    response = requests.post(url, headers=headers, params=payload)")
                sb.append("    assert response.status_code == 201, 'Login failed'")
                sb.append("    token = response.json().get('data', {}).get('jwt')")
                sb.append("    return f'Bearer {token}'")
            else:
                sb.append("    return basic_auth")
            sb.append("")
        
        # Test functions
        for tc in test_cases:
            auth_arg = "authorization" if needs_auth and tc.includeAuth else ""
            if auth_arg:
                sb.append(f"def {tc.methodName}({auth_arg}):")
            else:
                sb.append(f"def {tc.methodName}():")
            
            sb.append(f"    \"\"\"{tc.description}\"\"\"")
            sb.append(f"    url = f'{{BASE_URL}}{tc.endpoint}'")
            
            headers = tc.headers.copy() if tc.headers else {}
            if needs_auth and tc.includeAuth and is_bearer_auth:
                headers['authorization'] = '{authorization}'
            
            if headers:
                headers_str = json.dumps(headers).replace('"{authorization}"', 'authorization')
                sb.append(f"    headers = {headers_str}")
            else:
                sb.append("    headers = {}")
                
            params = tc.queryParams.copy() if tc.queryParams else {}
            if needs_auth and tc.includeAuth and not is_bearer_auth:
                params['authorization'] = '{authorization}'
                
            if params:
                params_str = json.dumps(params).replace('"{authorization}"', 'authorization')
                sb.append(f"    params = {params_str}")
            else:
                sb.append("    params = {}")
            
            is_multipart = getattr(tc, 'contentType', None) == "multipart/form-data"
            file_fields = getattr(tc, 'fileFields', {})
            
            # If the body contains a 'dto' root key or we have fileFields, ensure it's treated as multipart
            if not is_multipart and (bool(file_fields) or (isinstance(tc.body, dict) and "dto" in tc.body)):
                is_multipart = True
                if not file_fields:
                    file_fields = {"logo": "image/png", "favicon": "image/png"}

            if is_multipart and tc.body:
                # --- WISH 2: multipart branch ---
                body_to_use = tc.body
                fields_to_use = getattr(tc, 'testDataFields', []) or []
                
                # Unwrap 'dto' key to avoid doubly-wrapping the payload in multipart forms
                if isinstance(tc.body, dict) and "dto" in tc.body:
                    body_to_use = tc.body["dto"]
                    fields_to_use = [f[4:] if f.startswith("dto.") else f for f in fields_to_use]
                
                if getattr(tc, 'useRandomTestData', False) and getattr(tc, 'testDataFields', None):
                    sb.append(f"    _rnd = random.randint(10000, 99999)")
                    payload_str = self._build_random_payload_str(body_to_use, fields_to_use, tc.testDataPrefix)
                    sb.append(f"    dto = {payload_str}")
                else:
                    payload_str = json.dumps(body_to_use, indent=4).replace('\n', '\n    ')
                    sb.append(f"    dto = {payload_str}")
                    
                sb.append("")
                sb.append(f"    # ✅ Fake in-memory files (no real files needed)")
                for field_name, mime_type in file_fields.items():
                    sb.append(f'    fake_{field_name} = io.BytesIO(b"fake image content")')
                sb.append("")
                
                sb.append(f"    files = {{")
                sb.append(f'        "dto": (None, json.dumps(dto), "application/json"),')
                for field_name, mime_type in file_fields.items():
                    sb.append(f'        "{field_name}": ("{field_name}.png", fake_{field_name}, "{mime_type}"),')
                sb.append(f"    }}")
                sb.append("")
                sb.append(f"    # Build request (for debug)")
                sb.append(f"    req = requests.Request('{tc.httpMethod}', url, headers=headers, params=params, files=files)")

            elif tc.body:
                if getattr(tc, 'useRandomTestData', False) and tc.testDataFields:
                    sb.append(f"    _rnd = random.randint(10000, 99999)")
                    payload_str = self._build_random_payload_str(tc.body, tc.testDataFields, tc.testDataPrefix)
                    sb.append(f"    payload = {payload_str}")
                elif isinstance(tc.body, dict):
                    payload_str = json.dumps(tc.body, indent=4).replace('\n', '\n    ')
                    sb.append(f"    payload = {payload_str}")
                else:
                    payload_str = json.dumps(tc.body, indent=4).replace('\n', '\n    ')
                    sb.append(f"    payload = {payload_str}")
                if isinstance(tc.body, dict):
                    sb.append(f"    req = requests.Request('{tc.httpMethod}', url, headers=headers, params=params, json=payload)")
                else:
                    sb.append(f"    req = requests.Request('{tc.httpMethod}', url, headers=headers, params=params, data=payload)")

            else:
                sb.append(f"    req = requests.Request('{tc.httpMethod}', url, headers=headers, params=params)")

            # --- WISH 1: debug print + prepare/send (same for ALL branches) ---
            sb.append(f"    prepared = req.prepare()")
            sb.append(f"    print('\\n--- REQUEST DATA ---')")
            sb.append(f"    print('request_data:', prepared.body)")
            sb.append(f"    session = requests.Session()")
            sb.append(f"    response = session.send(prepared)")
            sb.append(f"    print('\\n--- RESPONSE DATA ---')")
            sb.append(f"    print('response_data:', response.text)")
            
            sb.append("")
            sb.append(f"    assert response.status_code == {tc.expectedStatus}, f'Expected {tc.expectedStatus}, got {{response.status_code}}'")
            
            if tc.validateResponseStructure:
                sb.append("    data = response.json()")
                for field in ['path', 'time', 'message', 'code', 'data']:
                    sb.append(f"    assert '{field}' in data, 'Response should have {field} field'")
                    
            if tc.responseFieldAssertions:
                sb.append("    data = response.json()")
                for key, val in tc.responseFieldAssertions.items():
                    if key == "_jsonSchema": continue
                    parts = key.split('.')
                    path_expr = 'data'
                    for p in parts:
                        path_expr += f"['{p}']"
                    
                    if val == "notNull":
                        sb.append(f"    assert {path_expr} is not None, '{key} should not be null'")
                    elif isinstance(val, (int, bool)):
                        sb.append(f"    assert {path_expr} == {val}, '{key} should be {val}'")
                    else:
                        sb.append(f"    assert {path_expr} == '{val}', '{key} should be {val}'")
            
            sb.append("")
        
        return "\n".join(sb)

    def _build_random_payload_str(self, body: dict, test_data_fields: list, prefix: str) -> str:
        """Build a Python dict literal string where testDataFields paths use f-string random values."""
        modified = copy.deepcopy(body)
        replacements = {}

        for field_path in test_data_fields:
            parts = field_path.split('.')
            obj = modified
            for part in parts[:-1]:
                if isinstance(obj, dict) and part in obj:
                    obj = obj[part]
                else:
                    obj = None
                    break
            if obj is None:
                continue
            last_key = parts[-1]
            if isinstance(obj, dict) and last_key in obj:
                placeholder = f"@@RANDOM_{last_key}@@"
                if 'email' in last_key.lower():
                    replacements[f'"{placeholder}"'] = f'f"{prefix}{{_rnd}}@gmail.com"'
                else:
                    replacements[f'"{placeholder}"'] = f'f"{prefix}{{_rnd}}"'
                obj[last_key] = placeholder

        # Pretty format with indentation
        raw = json.dumps(modified, indent=4)
        for placeholder, fstr in replacements.items():
            # Replace placeholder with string without quotes (fstr has its own quotes if needed, 
            # actually we are replacing '"@@RANDOM_xxx@@"' with 'f"prefix{_rnd}"')
            raw = raw.replace(f'"{placeholder}"', fstr)
            raw = raw.replace(placeholder, fstr) # fallback
            
        # Indent multiple lines to align properly with code block
        raw = raw.replace('\n', '\n    ')
        return raw

    def build_file_name(self, endpoint: str) -> str:
        parts = endpoint.strip("/").split("/")
        clean_parts = []
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                continue
            clean = ''.join(c for c in part if c.isalnum())
            if clean:
                clean_parts.append(clean.lower())
        base = "_".join(clean_parts) if clean_parts else "endpoint"
        return f"test_{base}.py"