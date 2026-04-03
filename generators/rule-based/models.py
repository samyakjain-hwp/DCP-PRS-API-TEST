from typing import Dict, Any, Optional

class ApiSpec:
    def __init__(self, data: Dict[str, Any]):
        self.apiName: str = data.get("apiName", "")
        self.baseUrl: str = data.get("baseUrl", "")
        self.endpoint: str = data.get("endpoint", "")
        self.method: str = data.get("method", "GET").upper()
        self.headers: Dict[str, str] = data.get("headers", {})
        self.queryParams: Dict[str, str] = data.get("queryParams", {})
        self.username: Optional[str] = data.get("username")
        self.password: Optional[str] = data.get("password")
        self.body: Any = data.get("body")
        self.contentType: Optional[str] = data.get("contentType")
        self.authType: Optional[str] = data.get("authType")
        self.fileFields: Dict[str, str] = data.get("fileFields", {})
        self.expectedStatus: int = data.get("expectedStatus", 200)
        self.expectedResponseFields: Dict[str, Any] = data.get("expectedResponseFields", {})
        self.responseSchema: Dict[str, Any] = data.get("responseSchema", {})

class TestCase:
    def __init__(self):
        self.methodName: str = ""
        self.description: str = ""
        self.httpMethod: str = ""
        self.endpoint: str = ""
        self.headers: Dict[str, str] = {}
        self.queryParams: Dict[str, str] = {}
        self.body: Any = None
        self.expectedStatus: int = 200
        self.validateResponseStructure: bool = False
        self.includeAuth: bool = True
        self.responseFieldAssertions: Dict[str, Any] = {}
