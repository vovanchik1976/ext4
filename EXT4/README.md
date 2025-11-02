# Ext4 GUI

Графическое приложение для работы с файловой системой ext4 на Windows.

## Описание

Ext4 GUI - это приложение с графическим интерфейсом, позволяющее:
- Открывать образы файловой системы ext4
- Просматривать содержимое файловой системы
- Создавать, удалять и переименовывать файлы и директории
- Импортировать и экспортировать файлы между Windows и ext4
- Форматировать новые образы ext4

Приложение написано на Python с использованием PyQt5 для интерфейса и C-библиотеки libext2fs для работы с файловой системой.

## Структура проекта

```
ext4_gui/
├── .venv/                    # Виртуальное окружение Python
├── build_logs/               # Логи сборки и тестов
│   ├── e2fsprogs_build.log
│   ├── shim_build.log
│   └── test_run.log
├── extern/e2fsprogs/         # Исходный код e2fsprogs
├── native/ext4shim/          # C-ши́м для взаимодействия с libext2fs
│   ├── ext4shim.c
│   ├── ext4shim.h
│   ├── ext4shim.def
│   ├── build_shim.bat
│   └── bin/ext4shim.dll     # Скомпилированная библиотека (нужно скомпилировать)
├── src/                      # Исходный код Python
│   ├── ext4fs.py
│   └── main_qt.py
├── tests/                    # Тесты
│   └── smoke_test.py
├── REPORT.md                 # Подробный отчет о сборке
└── README.md                 # Этот файл
```

## Требования

- Windows 7 или выше
- Python 3.13 x64
- MSYS2 с MinGW-w64
- Qt 5.15

## Установка

1. Установите Python 3.13 x64

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Установите MSYS2 и необходимые пакеты:
   ```bash
   pacman -S --needed git autoconf automake libtool pkgconf make \
     mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
     mingw-w64-x86_64-zlib \
     mingw-w64-x86_64-qt5-base mingw-w64-x86_64-qt5-tools \
     mingw-w64-x86_64-qt5-svg mingw-w64-x86_64-qt5-imageformats mingw-w64-x86_64-qt5-winextras
   ```

4. Соберите e2fsprogs для MinGW64 (см. REPORT.md)

5. Соберите ext4shim.dll:
   ```cmd
   cd native/ext4shim
   build_shim.bat
   ```

## Использование

Запустите приложение:
```bash
python src/main_qt.py
```

В графическом интерфейсе доступны следующие функции:
- Open Image: Открыть существующий образ ext4
- Format Image: Создать и форматировать новый образ ext4
- Import File: Импортировать файл из Windows в образ ext4
- New Folder: Создать новую директорию
- Rename: Переименовать выбранный элемент
- Delete: Удалить выбранный элемент
- Export: Экспортировать файл из образа ext4 в Windows
- Properties: Показать свойства выбранного элемента

## Архитектура

Проект состоит из трех основных компонентов:

1. **C-ши́м (ext4shim.dll)**: Обеспечивает интерфейс между Python и библиотекой libext2fs
2. **Python-обёртка (ext4fs.py)**: Предоставляет объектно-ориентированный интерфейс для работы с ext4
3. **GUI (main_qt.py)**: Графический интерфейс пользователя на базе PyQt5

## Лицензия

Проект распространяется под лицензией MIT. См. файл LICENSE для подробной информации.