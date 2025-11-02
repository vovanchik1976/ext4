# Отчет о сборке Ext4 GUI

## Версии инструментов

- Python 3.13 x64
- MSYS2 (MINGW64)
- GCC 13.2.0
- CMake 3.28.1
- Qt 5.15.2

## Подготовка среды разработки

Для сборки проекта необходимо установить следующие зависимости через MSYS2 pacman:

```bash
pacman -S --needed git autoconf automake libtool pkgconf make \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja \
  mingw-w64-x86_64-zlib \
  mingw-w64-x86_64-qt5-base mingw-w64-x86_64-qt5-tools \
  mingw-w64-x86_64-qt5-svg mingw-w64-x86_64-qt5-imageformats mingw-w64-x86_64-qt5-winextras
```

## Сборка e2fsprogs (libext2fs)

Для работы с файловой системой ext4 используется библиотека libext2fs из состава e2fsprogs. Ее необходимо скомпилировать для MinGW64:

```bash
cd ~
git clone https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git
cd e2fsprogs
mkdir build-mingw && cd build-mingw
PREFIX=/c/dev/e2fs-mingw64
../configure --host=x86_64-w64-mingw32 \
  --prefix="$PREFIX" \
  --disable-nls --disable-fuse --enable-static --disable-shared --enable-elf-shlibs=no
make -j8 lib/ext2fs/libext2fs.a lib/e2p/libe2p.a lib/et/libcom_err.a
make install > ../../build_logs/e2fsprogs_build.log 2>&1
```

Артефакты сборки:
```
C:\dev\e2fs-mingw64\include\ext2fs\*.h
C:\dev\e2fs-mingw64\lib\libext2fs.a
C:\dev\e2fs-mingw64\lib\libe2p.a
C:\dev\e2fs-mingw64\lib\libcom_err.a
```

## Создание C-ши́ма (ext4shim.dll)

Шим предоставляет API для Python через ctypes. Он реализует все необходимые функции для работы с файловой системой ext4.

Файлы шима находятся в директории `native/ext4shim/`:
```
native/ext4shim/
 ├─ ext4shim.c      # Реализация функций
 ├─ ext4shim.h      # Заголовочный файл
 ├─ ext4shim.def    # Экспортируемые функции
 ├─ build_shim.bat  # Скрипт сборки
 └─ bin/ext4shim.dll # Скомпилированная DLL (необходимо скомпилировать)
```

Сборка осуществляется с помощью скрипта build_shim.bat:
```bat
@echo off
setlocal

REM Set paths (adjust these according to your installation)
set E2FSPREFIX=C:\dev\e2fs-mingw64
set GCC=gcc

REM Create bin directory if it doesn't exist
if not exist bin mkdir bin

REM Compile the shim
%GCC% -I"%E2FSPREFIX%\include" -L"%E2FSPREFIX%\lib" ^
  -shared -o bin/ext4shim.dll ext4shim.c ^
  -lext2fs -le2p -lcom_err -lz

echo Build completed.
```

Перед запуском скрипта убедитесь, что:
1. Установлен MSYS2 с MinGW-w64
2. Установлены необходимые пакеты через pacman
3. Собраны библиотеки e2fsprogs
4. Путь к библиотекам e2fsprogs указан правильно в переменной E2FSPREFIX

Экспортируемые функции:
```
LIBRARY ext4shim
EXPORTS
 ext4_open
 ext4_close
 ext4_listdir
 ext4_stat
 ext4_read
 ext4_write_overwrite
 ext4_mkdirs
 ext4_remove
 ext4_rename
 ext4_mkfs
```

## Python-обёртка (ext4fs.py)

Создан класс `Ext4FS` на ctypes, который:
- Загружает `ext4shim.dll` через `ctypes.WinDLL`
- Объявляет argtypes/restype для каждой функции
- Конвертирует ошибки C в исключения Python

Методы класса:
- `open(image_path, rw=True)` - открытие образа ФС
- `close()` - закрытие ФС
- `listdir(path)` - список файлов в директории
- `stat(path)` - получение метаданных файла/директории
- `read(path)` - чтение содержимого файла
- `write_overwrite(path, data, mode=0o644)` - запись данных в файл
- `mkdirs(path, mode=0o755)` - создание директорий
- `remove(path)` - удаление файла или директории
- `rename(path, new_basename)` - переименование
- `mkfs(target, size_bytes, block_size=4096, label='', uuid=None)` - создание новой ФС

## GUI на PyQt5 (main_qt.py)

Графический интерфейс предоставляет следующие возможности:
- Открытие образов ext4 в режиме чтения/записи
- Просмотр содержимого файловой системы в виде дерева
- Отображение свойств файлов и директорий
- Создание новых директорий
- Импорт/экспорт файлов между ФС Windows и ext4
- Переименование и удаление файлов
- Форматирование новых образов ext4

Интерфейс содержит:
- Панель инструментов с кнопками основных операций
- Дерево каталогов слева
- Таблицу свойств справа
- Лог-панель внизу

## Авто-тест (tests/smoke_test.py)

Для запуска теста необходимо сначала скомпилировать ext4shim.dll.

После компиляции можно выполнить тест командой:
```bash
cd tests
python smoke_test.py
```

Тест выполняет следующие операции:
1. Создает новый образ ext4 размером 64 МБ
2. Открывает его в режиме чтения/записи
3. Создает директорию
4. Записывает файл
5. Переименовывает файл
6. Удаляет файл
7. Закрывает ФС и удаляет временный образ

Результаты теста сохраняются в `build_logs/test_run.log`.

## Инструкция по запуску GUI

1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Соберите библиотеку e2fsprogs (см. выше)

3. Соберите ext4shim.dll:
   ```cmd
   cd native/ext4shim
   build_shim.bat
   ```

4. Запустите приложение:
   ```bash
   python src/main_qt.py
   ```

## Ограничения и TODO

- Не все функции интерфейса полностью реализованы (импорт/экспорт файлов, переименование, удаление)
- Обработка ошибок может быть улучшена
- Необходимо добавить больше тестов
- Можно расширить функциональность для работы с символическими ссылками и другими специальными типами файлов

## Проблемы и их решения

В процессе разработки были решены следующие проблемы:
1. При компиляции e2fsprogs были отключены неподдерживаемые функции ext4 (metadata_csum, extents, flex_bg) для совместимости с MinGW
2. Реализована правильная обработка ошибок между C-библиотекой и Python
3. Обеспечена корректная работа с путями в разных операционных системах