class ApiError(Exception):
    """Исключение при неправильно ответе API."""


class ApiKeyError(Exception):
    """Вответе API отсутсвуют запрошенные поля."""


class BadResponse(Exception):
    """Если сервер API возвращает код статуса отличный от 200."""
