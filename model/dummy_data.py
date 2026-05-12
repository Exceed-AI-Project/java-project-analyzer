import json

_DUMMY_CLASSES = [
    {"클래스명": "UserController",  "패키지": "com.example.controller",  "메소드 수": 4, "타입": "Class"},
    {"클래스명": "UserService",     "패키지": "com.example.service",     "메소드 수": 6, "타입": "Class"},
    {"클래스명": "UserRepository",  "패키지": "com.example.repository",  "메소드 수": 3, "타입": "Interface"},
    {"클래스명": "User",            "패키지": "com.example.model",       "메소드 수": 8, "타입": "Class"},
    {"클래스명": "OrderController", "패키지": "com.example.controller",  "메소드 수": 5, "타입": "Class"},
    {"클래스명": "OrderService",    "패키지": "com.example.service",     "메소드 수": 7, "타입": "Class"},
    {"클래스명": "OrderRepository", "패키지": "com.example.repository",  "메소드 수": 4, "타입": "Interface"},
    {"클래스명": "Order",           "패키지": "com.example.model",       "메소드 수": 6, "타입": "Class"},
]

_DUMMY_METHODS = [
    {"클래스": "UserController",  "메소드명": "getUsers",    "반환 타입": "List<User>",     "파라미터": "",             "접근제한자": "public"},
    {"클래스": "UserController",  "메소드명": "getUserById", "반환 타입": "User",           "파라미터": "Long id",      "접근제한자": "public"},
    {"클래스": "UserController",  "메소드명": "createUser",  "반환 타입": "User",           "파라미터": "UserDto dto",  "접근제한자": "public"},
    {"클래스": "UserController",  "메소드명": "deleteUser",  "반환 타입": "void",           "파라미터": "Long id",      "접근제한자": "public"},
    {"클래스": "UserService",     "메소드명": "findAll",     "반환 타입": "List<User>",     "파라미터": "",             "접근제한자": "public"},
    {"클래스": "UserService",     "메소드명": "findById",    "반환 타입": "Optional<User>", "파라미터": "Long id",      "접근제한자": "public"},
    {"클래스": "UserService",     "메소드명": "save",        "반환 타입": "User",           "파라미터": "User user",    "접근제한자": "public"},
    {"클래스": "UserService",     "메소드명": "delete",      "반환 타입": "void",           "파라미터": "Long id",      "접근제한자": "public"},
    {"클래스": "OrderController", "메소드명": "getOrders",   "반환 타입": "List<Order>",    "파라미터": "",             "접근제한자": "public"},
    {"클래스": "OrderController", "메소드명": "createOrder", "반환 타입": "Order",          "파라미터": "OrderDto dto", "접근제한자": "public"},
    {"클래스": "OrderService",    "메소드명": "findAll",     "반환 타입": "List<Order>",    "파라미터": "",             "접근제한자": "public"},
    {"클래스": "OrderService",    "메소드명": "createOrder", "반환 타입": "Order",          "파라미터": "OrderDto dto", "접근제한자": "public"},
]

_DUMMY_CALL_GRAPH = [
    {"호출자 클래스": "UserController",  "호출자 메소드": "getUsers",    "피호출 클래스": "UserService",    "피호출 메소드": "findAll"},
    {"호출자 클래스": "UserController",  "호출자 메소드": "getUserById", "피호출 클래스": "UserService",    "피호출 메소드": "findById"},
    {"호출자 클래스": "UserController",  "호출자 메소드": "createUser",  "피호출 클래스": "UserService",    "피호출 메소드": "save"},
    {"호출자 클래스": "UserController",  "호출자 메소드": "deleteUser",  "피호출 클래스": "UserService",    "피호출 메소드": "delete"},
    {"호출자 클래스": "UserService",     "호출자 메소드": "findAll",     "피호출 클래스": "UserRepository", "피호출 메소드": "findAll"},
    {"호출자 클래스": "UserService",     "호출자 메소드": "findById",    "피호출 클래스": "UserRepository", "피호출 메소드": "findById"},
    {"호출자 클래스": "OrderController", "호출자 메소드": "getOrders",   "피호출 클래스": "OrderService",   "피호출 메소드": "findAll"},
    {"호출자 클래스": "OrderController", "호출자 메소드": "createOrder", "피호출 클래스": "OrderService",   "피호출 메소드": "createOrder"},
    {"호출자 클래스": "OrderService",    "호출자 메소드": "createOrder", "피호출 클래스": "UserRepository", "피호출 메소드": "findById"},
]

_DUMMY_ENDPOINTS = [
    {"메소드": "GET",    "경로": "/api/users",      "컨트롤러": "UserController",  "핸들러": "getUsers",    "파라미터": ""},
    {"메소드": "GET",    "경로": "/api/users/{id}", "컨트롤러": "UserController",  "핸들러": "getUserById", "파라미터": "id (Path)"},
    {"메소드": "POST",   "경로": "/api/users",      "컨트롤러": "UserController",  "핸들러": "createUser",  "파라미터": "UserDto (Body)"},
    {"메소드": "DELETE", "경로": "/api/users/{id}", "컨트롤러": "UserController",  "핸들러": "deleteUser",  "파라미터": "id (Path)"},
    {"메소드": "GET",    "경로": "/api/orders",     "컨트롤러": "OrderController", "핸들러": "getOrders",   "파라미터": ""},
    {"메소드": "POST",   "경로": "/api/orders",     "컨트롤러": "OrderController", "핸들러": "createOrder", "파라미터": "OrderDto (Body)"},
]

_DUMMY_SIM_RESPONSES = {
    "GET":    {"status": 200, "body": {"id": 1, "name": "홍길동", "email": "hong@example.com", "createdAt": "2025-01-15"}},
    "POST":   {"status": 201, "body": {"id": 99, "name": "신규 사용자", "created": True}},
    "DELETE": {"status": 204, "body": None},
}

_METHOD_ICON = {"GET": "🟢", "POST": "🔵", "PUT": "🟡", "DELETE": "🔴", "PATCH": "🟠"}

_SIM_DEFAULT_BODY = json.dumps(
    {"name": "홍길동", "email": "hong@example.com"},
    ensure_ascii=False,
    indent=2,
)
