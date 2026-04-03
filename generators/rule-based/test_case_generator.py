import copy
from typing import List, Dict, Any
from models import ApiSpec, TestCase

class TestCaseGenerator:
    def generate(self, spec: ApiSpec) -> List[TestCase]:
        tests: List[TestCase] = []
        name_prefix = self._build_name_prefix(spec.endpoint)

        has_credentials = bool(spec.username and spec.password)
        is_bearer_auth = spec.authType == "BEARER"
        needs_auth = has_credentials or is_bearer_auth

        clean_headers = self._clean_headers(spec)

        # 1. Happy path
        happy = TestCase()
        happy.methodName = f"test_{name_prefix}_success"
        happy.description = f"Verify {spec.apiName} returns {spec.expectedStatus} with valid request"
        happy.httpMethod = spec.method
        happy.endpoint = spec.endpoint
        happy.headers = copy.deepcopy(clean_headers)
        happy.queryParams = copy.deepcopy(spec.queryParams)
        happy.body = spec.body
        happy.expectedStatus = spec.expectedStatus
        happy.validateResponseStructure = True
        tests.append(happy)

        # 2. Auth-specific negative tests
        if needs_auth:
            missing_auth = TestCase()
            missing_auth.methodName = f"test_{name_prefix}_missing_authorization"
            missing_auth.description = f"Verify {spec.apiName} fails when authorization is missing"
            missing_auth.httpMethod = spec.method
            missing_auth.endpoint = spec.endpoint
            missing_auth.headers = copy.deepcopy(clean_headers)
            missing_auth.queryParams = {}
            missing_auth.body = spec.body
            missing_auth.expectedStatus = 401
            missing_auth.includeAuth = False
            missing_auth.validateResponseStructure = False
            tests.append(missing_auth)

            invalid_auth = TestCase()
            invalid_auth.methodName = f"test_{name_prefix}_invalid_authorization"
            invalid_auth.description = f"Verify {spec.apiName} fails when authorization is invalid"
            invalid_auth.httpMethod = spec.method
            invalid_auth.endpoint = spec.endpoint
            invalid_headers = copy.deepcopy(clean_headers)
            if is_bearer_auth:
                invalid_headers["authorization"] = "Bearer INVALID_TOKEN"
            else:
                invalid_headers["authorization"] = "Basic INVALID_CREDENTIALS"
            invalid_auth.headers = invalid_headers
            invalid_auth.queryParams = copy.deepcopy(spec.queryParams)
            invalid_auth.body = spec.body
            invalid_auth.expectedStatus = 401
            invalid_auth.includeAuth = False
            invalid_auth.validateResponseStructure = False
            tests.append(invalid_auth)

        # 3 & 4. Params
        if spec.queryParams:
            for param_key in spec.queryParams.keys():
                missing = TestCase()
                missing.methodName = f"test_{name_prefix}_missing_{param_key}"
                missing.description = f"Verify {spec.apiName} fails when {param_key} param is missing"
                missing.httpMethod = spec.method
                missing.endpoint = spec.endpoint
                missing.headers = copy.deepcopy(clean_headers)
                missing.queryParams = copy.deepcopy(spec.queryParams)
                missing.queryParams.pop(param_key, None)
                missing.body = spec.body
                missing.expectedStatus = 400
                tests.append(missing)

                invalid = TestCase()
                invalid.methodName = f"test_{name_prefix}_invalid_{param_key}"
                invalid.description = f"Verify {spec.apiName} fails when {param_key} has invalid value"
                invalid.httpMethod = spec.method
                invalid.endpoint = spec.endpoint
                invalid.headers = copy.deepcopy(clean_headers)
                invalid.queryParams = copy.deepcopy(spec.queryParams)
                invalid.queryParams[param_key] = f"INVALID_VALUE_{param_key}"
                invalid.body = spec.body
                invalid.expectedStatus = 400
                tests.append(invalid)

        # 5. Wrong HTTP method
        wrong_method = TestCase()
        alt_method = "GET" if spec.method.upper() == "POST" else "POST"
        wrong_method.methodName = f"test_{name_prefix}_wrong_method"
        wrong_method.description = f"Verify {spec.apiName} rejects {alt_method} method"
        wrong_method.httpMethod = alt_method
        wrong_method.endpoint = spec.endpoint
        wrong_method.headers = copy.deepcopy(clean_headers)
        wrong_method.queryParams = copy.deepcopy(spec.queryParams)
        wrong_method.body = spec.body
        wrong_method.expectedStatus = 405
        tests.append(wrong_method)

        # 6. Response structure validation
        structure = TestCase()
        structure.methodName = f"test_{name_prefix}_response_structure"
        structure.description = f"Verify {spec.apiName} response has expected structure fields"
        structure.httpMethod = spec.method
        structure.endpoint = spec.endpoint
        structure.headers = copy.deepcopy(clean_headers)
        structure.queryParams = copy.deepcopy(spec.queryParams)
        structure.body = spec.body
        structure.expectedStatus = spec.expectedStatus
        structure.validateResponseStructure = True
        tests.append(structure)

        # 7. Schema validation
        has_expected_fields = bool(spec.expectedResponseFields)
        has_schema = bool(spec.responseSchema)
        if has_expected_fields or has_schema:
            schema = TestCase()
            schema.methodName = f"test_{name_prefix}_schema_validation"
            schema.description = f"Verify {spec.apiName} response matches expected schema"
            schema.httpMethod = spec.method
            schema.endpoint = spec.endpoint
            schema.headers = copy.deepcopy(clean_headers)
            schema.queryParams = copy.deepcopy(spec.queryParams)
            schema.body = spec.body
            schema.expectedStatus = spec.expectedStatus
            if has_expected_fields:
                schema.responseFieldAssertions = copy.deepcopy(spec.expectedResponseFields)
            else:
                schema.responseFieldAssertions = {"_jsonSchema": True}
            tests.append(schema)

        return tests

    def _build_name_prefix(self, endpoint: str) -> str:
        parts = endpoint.strip("/").split("/")
        clean_parts = []
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                continue
            clean = ''.join(c for c in part if c.isalnum())
            if clean:
                clean_parts.append(clean.lower())
        return "_".join(clean_parts) if clean_parts else "endpoint"

    def _clean_headers(self, spec: ApiSpec) -> Dict[str, str]:
        headers = copy.deepcopy(spec.headers) if spec.headers else {}
        if spec.authType:
            headers.pop("authorization", None)
            headers.pop("Authorization", None)
        if spec.contentType == "multipart/form-data":
            headers.pop("content-type", None)
            headers.pop("Content-Type", None)
        return headers
