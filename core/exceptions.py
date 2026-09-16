"""Иерархия исключений для PSP Toolkit."""


class PSPToolkitError(Exception):
    """Базовое исключение для всех ошибок приложения."""


class BinaryFormatError(PSPToolkitError):
    """Ошибка валидации или чтения бинарного формата."""


class SFOFormatError(BinaryFormatError):
    """Ошибка разбора или сборки файла PARAM.SFO."""


class ISOFormatError(BinaryFormatError):
    """Ошибка разбора или чтения структуры ISO 9660."""


class CSOFormatError(BinaryFormatError):
    """Ошибка сжатия или распаковки формата CSO."""


class PBPFormatError(BinaryFormatError):
    """Ошибка разбора или сборки контейнера PBP."""


class CUEFormatError(BinaryFormatError):
    """Ошибка разбора разметки CUE Sheet."""