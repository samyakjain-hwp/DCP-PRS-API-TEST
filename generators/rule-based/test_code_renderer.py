import json
from typing import List, Dict, Any
from models import ApiSpec, TestCase

class TestCodeRenderer:
    def render(self, spec: ApiSpec, test_cases: List[TestCase]) -> str:
        sb = []
        sb.append("import pytest")
        sb.append("import requests")
        sb.append("import base64")
        sb.append("import os")
        sb.append("import json")
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
            
            if tc.body:
                if isinstance(tc.body, dict):
                    sb.append(f"    payload = {json.dumps(tc.body)}")
                    sb.append(f"    response = requests.request('{tc.httpMethod}', url, headers=headers, params=params, json=payload)")
                else:
                    sb.append(f"    payload = {json.dumps(tc.body)}")
                    sb.append(f"    response = requests.request('{tc.httpMethod}', url, headers=headers, params=params, data=payload)")
            else:
                sb.append(f"    response = requests.request('{tc.httpMethod}', url, headers=headers, params=params)")
            
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
