import sys
import os
import json
import re
import shlex
from urllib.parse import urlparse, parse_qs, unquote
import importlib.util

# Load schemaInferrer dynamically
helper_path = os.path.join(os.path.dirname(__file__), "..", "helpers", "SchemaInferrer.py")
spec_inferrer = importlib.util.spec_from_file_location("schemaInferrer", helper_path)
schemaInferrer = importlib.util.module_from_spec(spec_inferrer)
spec_inferrer.loader.exec_module(schemaInferrer)

SPECS_DIR = "api-specs"
SKIP_HEADERS = {
    "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site",
    "user-agent", "origin", "referer", "priority", "cookie",
    "accept-language"
}
RESPONSE_SEPARATOR = "---RESPONSE---"

def parse_json_body(body_str):
    try:
        return json.loads(body_str)
    except Exception:
        return body_str

def parse_url_encoded_body(body_str):
    fields = {}
    for pair in body_str.split("&"):
        if "=" in pair:
            key, val = pair.split("=", 1)
            fields[unquote(key)] = unquote(val)
        else:
            fields[unquote(pair)] = ""
    return fields

def parse_multipart_body(body_str, content_type):
    boundary_match = re.search(r"boundary=([^\s;]+)", content_type)
    boundary = boundary_match.group(1) if boundary_match else None

    if not boundary:
        lines = body_str.split("\n", 1)
        if lines and lines[0].strip().startswith("--"):
            boundary = lines[0].strip()[2:]

    fields = {}
    if not boundary:
        fields["_raw"] = body_str
        return fields

    delimiter = "--" + boundary
    parts = body_str.split(delimiter)

    for part in parts:
        if not part.strip() or part.strip() == "--":
            continue

        name_match = re.search(r'name="([^"]+)"', part)
        if not name_match:
            continue
        name = name_match.group(1)

        part_headers = part.split("\r\n\r\n", 1)[0] if "\r\n\r\n" in part else part.split("\n\n", 1)[0]
        is_json_part = "content-type: application/json" in part_headers.lower()

        filename_match = re.search(r'filename="([^"]+)"', part)
        has_filename = bool(filename_match)

        segments = part.split("\r\n\r\n", 1)
        if len(segments) == 1:
            segments = part.split("\n\n", 1)

        if len(segments) > 1:
            val = segments[1].strip()
            if val.endswith("--"):
                val = val[:-2].strip()

            if is_json_part:
                fields[name] = "{{json:" + val + "}}"
            elif has_filename:
                fields[name] = "{{file:" + filename_match.group(1) + "}}"
            else:
                fields[name] = val

    return fields

def build_api_name(path):
    parts = [p for p in path.lstrip("/").split("/") if p and not re.match(r"v\d+", p)]
    clean_parts = [re.sub(r"[^a-zA-Z0-9]", "", p) for p in parts]
    return " ".join([p.capitalize() for p in clean_parts if p])

def build_file_name(path):
    parts = [p for p in path.lstrip("/").split("/") if p and not re.match(r"v\d+", p)]
    return "-".join([p.lower() for p in parts if p])

def tokenize(input_str):
    try:
        tokens = shlex.split(input_str)
    except ValueError:
        tokens = input_str.split()
    
    processed = []
    for t in tokens:
        if t.startswith("$'") and t.endswith("'"):
            t = t[2:-1]
            t = t.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")
        processed.append(t)
    return processed

def build_expected_fields(data, prefix, result):
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if v is None:
                continue
            elif isinstance(v, dict):
                build_expected_fields(v, key, result)
            elif isinstance(v, list):
                result[key] = "notNull"
            elif isinstance(v, bool):
                result[key] = v
            elif isinstance(v, (int, float)):
                result[key] = v
            else:
                result[key] = "notNull"

def detect_test_data_fields(data, prefix, result):
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                detect_test_data_fields(v, key, result)
            else:
                field_name = str(k)
                if any(x in field_name for x in ["email", "name", "Name", "username", "login"]) or field_name in ["collaborator", "firstName", "lastName"]:
                    result.append(key)

def parse_curl(curl_cmd):
    normalized = re.sub(r"\\\s*\n", " ", curl_cmd).strip()
    tokens = tokenize(normalized)

    url = None
    method = None
    body = None
    all_headers = {}
    form_parts = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "curl":
            i += 1
            continue
        if token in ["-X", "--request"]:
            i += 1
            if i < len(tokens): method = tokens[i].upper()
        elif token in ["-H", "--header"]:
            i += 1
            if i < len(tokens):
                h = tokens[i]
                if ":" in h:
                    k, v = h.split(":", 1)
                    all_headers[k.strip().lower()] = v.strip()
        elif token in ["-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"]:
            i += 1
            if i < len(tokens): body = tokens[i]
        elif token in ["-F", "--form"]:
            i += 1
            if i < len(tokens): form_parts.append(tokens[i])
        elif token in ["--compressed", "-k", "--insecure", "-L", "--location", "-v", "--verbose", "-s", "--silent"]:
            pass
        elif not token.startswith("-") and url is None:
            url = token
            
        i += 1

    if not url:
        raise ValueError("Could not find URL in curl command")

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port and parsed.port not in [80, 443]:
        base_url += f":{parsed.port}"

    query_params = {}
    if parsed.query:
        for pair in parsed.query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                k = unquote(k)
                if k.lower() == "authorization": continue
                query_params[k] = unquote(v)
            else:
                k = unquote(pair)
                if k.lower() == "authorization": continue
                query_params[k] = ""

    if not method:
        method = "POST" if (body or form_parts) else "GET"

    clean_headers = {}
    content_type = None
    has_bearer_auth = False

    for k, v in all_headers.items():
        if k in SKIP_HEADERS: continue

        if k == "authorization" and v.startswith("Bearer "):
            has_bearer_auth = True
            clean_headers["authorization"] = "Bearer {{token}}"
            continue

        if k == "content-type":
            content_type = v
            if "multipart/form-data" in v:
                clean_headers["content-type"] = "multipart/form-data"
            else:
                clean_headers[k] = v
            continue

        clean_headers[k] = v

    parsed_body = None
    file_fields = {}
    json_part_fields = []

    if form_parts:
        text_fields = {}
        content_type = "multipart/form-data"
        
        for form_part in form_parts:
            if "=" not in form_part:
                continue
            name, raw_val = form_part.split("=", 1)
            
            if raw_val.startswith("@"):
                file_path = raw_val[1:].strip('"')
                file_name = os.path.basename(file_path.replace("\\", "/"))
                file_fields[name] = file_name
                continue

            part_type = None
            val = raw_val
            if ";type=" in raw_val:
                val, part_type = raw_val.rsplit(";type=", 1)

            val = val.strip('"').replace('\\"', '"')

            if part_type and "application/json" in part_type:
                json_part_fields.append(name)
                text_fields[name] = parse_json_body(val)
            else:
                text_fields[name] = val
                
        parsed_body = text_fields
    elif body and content_type and "multipart/form-data" in content_type:
        multipart = parse_multipart_body(body, content_type)
        text_fields = {}
        
        for k, v in multipart.items():
            val_str = str(v)
            if val_str.startswith("{{file:"):
                file_fields[k] = val_str.replace("{{file:", "").replace("}}", "")
            elif val_str.startswith("{{json:"):
                json_str = val_str[7:-2]
                json_part_fields.append(k)
                text_fields[k] = parse_json_body(json_str)
            else:
                text_fields[k] = v
        parsed_body = text_fields
    elif body and content_type and "application/json" in content_type:
        parsed_body = parse_json_body(body)
    elif body and content_type and "application/x-www-form-urlencoded" in content_type:
        parsed_body = parse_url_encoded_body(body)
    elif body:
        trimmed = body.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            parsed_body = parse_json_body(body)
        else:
            parsed_body = body

    spec = {
        "apiName": build_api_name(parsed.path),
        "baseUrl": base_url,
        "endpoint": parsed.path,
        "method": method
    }

    if content_type and "multipart/form-data" in content_type:
        spec["contentType"] = "multipart/form-data"
    
    if has_bearer_auth:
        spec["authType"] = "BEARER"

    spec["headers"] = clean_headers
    spec["queryParams"] = query_params
    spec["body"] = parsed_body

    if file_fields:
        spec["fileFields"] = file_fields
    if json_part_fields:
        spec["jsonPartFields"] = json_part_fields

    spec["expectedStatus"] = 200
    spec["expectedResponseFields"] = {}
    spec["testDataPrefix"] = "autotest_"
    
    test_data_fields = []
    if isinstance(parsed_body, dict):
        detect_test_data_fields(parsed_body, "", test_data_fields)
    spec["testDataFields"] = test_data_fields

    return spec

def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Reading from: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            raw_input = f.read()
    else:
        print("Reading from stdin (paste and press Ctrl+D)...")
        raw_input = sys.stdin.read()

    if not raw_input.strip():
        print("ERROR: No input provided.", file=sys.stderr)
        sys.exit(1)

    curl_command = raw_input.strip()
    sample_response = None
    
    if RESPONSE_SEPARATOR in raw_input:
        idx = raw_input.index(RESPONSE_SEPARATOR)
        curl_command = raw_input[:idx].strip()
        sample_response = raw_input[idx + len(RESPONSE_SEPARATOR):].strip()
        print("Found sample response — will auto-generate responseSchema.")

    spec = parse_curl(curl_command)

    if sample_response:
        try:
            parsed_resp = json.loads(sample_response)
            schema = schemaInferrer.infer(parsed_resp)
            spec["responseSchema"] = schema
            print("  responseSchema generated from sample response.")

            if isinstance(parsed_resp, dict):
                fields = {}
                build_expected_fields(parsed_resp, "", fields)
                spec["expectedResponseFields"] = fields
                print("  expectedResponseFields generated from sample response.")

                if "code" in parsed_resp and isinstance(parsed_resp["code"], int):
                    spec["expectedStatus"] = parsed_resp["code"]
                    print(f"  expectedStatus set to {parsed_resp['code']} from sample response.")

        except Exception as e:
            print(f"  WARNING: Could not parse sample response as JSON: {e}")
            print("  Skipping responseSchema generation.")

    os.makedirs(SPECS_DIR, exist_ok=True)
    
    endpoint = spec.get("endpoint", "")
    filename = build_file_name(endpoint) + ".json"
    output_path = os.path.join(SPECS_DIR, filename)

    if os.path.exists(output_path):
        print(f"WARNING: {output_path} already exists — overwriting.")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    print(f"\\nGenerated: {output_path}")
    print(json.dumps(spec, indent=2))
    print("\\nNext steps:")
    print(f"  1. Review & edit {output_path}")
    print(f"     - Set expectedStatus (currently {spec.get('expectedStatus')})")
    if "responseSchema" in spec:
        print("     - Review auto-generated responseSchema")
    else:
        print("     - Add responseSchema or re-run with ---RESPONSE--- section")
    print(f"     - Review testDataFields (auto-detected: {spec.get('testDataFields')})")

if __name__ == "__main__":
    main()
