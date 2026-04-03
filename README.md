# API Test Generator (Python)

A tool to quickly generate API specifications from cURL commands, ported from the original Java implementation.

## Usage

### Generating Specs from cURL

Copy a cURL command from Chrome DevTools (right-click request > Copy > Copy as cURL) and save it to a file. Optionally, append `---RESPONSE---` followed by a sample JSON response to the same file to automatically infer the JSON Schema.

```bash
# Save your curl command to curl-inputs/curl-input.txt, then run:
python generators/curl_to_spec.py curl-inputs/curl-input.txt
```

This parses the cURL and generates an API spec JSON in `api-specs/`. Our implementation handles the following:

- **Core Generator (`generators/curl_to_spec.py`)**:
  - **cURL Parsing**: Processes files from `curl-inputs/` using `shlex` and `urllib.parse` to extract clean URL, method, headers, and body data.
  - **Header Sanitization**: Filters out browser noise (like `sec-ch-ua`, `referer`, `cookie`) and masks Bearer tokens with `{{token}}`.
  - **Payload Analysis**: Decodes JSON, URL-encoded, and complex `multipart/form-data` bodies, separating out `fileFields`.
  - **Test Data Auto-Detection**: Scans request bodies for fields like `email`, `firstName`, or `collaborator` to register them in `testDataFields`.
- **Schema Helper (`helpers/SchemaInferrer.py`)**:
  - **Response Inference**: When the input contains a `---RESPONSE---` section, this module dynamically generates a Draft-07 `responseSchema`.
  - **Structure Mapping**: Recursively determines types and required properties from sample JSON to populate `expectedResponseFields`.
- **Standardized Inputs (`curl-inputs/`)**:
  - Designed to hold raw text captures from Chrome DevTools, providing a single source of truth for generating specifications and managing sample payloads.
