<div align="center">

# 🪟 zapret-GUI — Windows

### Графический интерфейс для обхода замедления YouTube и Discord на Windows

Windows-версия GUI-концепта: та же PySide6-оболочка, но с нативным Windows-бэкендом
на **winws + WinDivert** (без bash-адаптера и WSL).

[![Релиз](https://img.shields.io/github/v/release/SkilinPur/zapret-GUI-Windows?color=8b5cf6&label=релиз&logo=github)](https://github.com/SkilinPur/zapret-GUI-Windows/releases)
[![Сборка](https://img.shields.io/github/actions/workflow/status/SkilinPur/zapret-GUI-Windows/build.yml?label=CI%20build)](https://github.com/SkilinPur/zapret-GUI-Windows/actions)
[![Платформа](https://img.shields.io/badge/Windows-10%2F11%20x64-0078d6?logo=windows&logoColor=white)]()
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)]()
[![UI](https://img.shields.io/badge/UI-PySide6-41cd52)]()
[![Движок](https://img.shields.io/badge/движок-winws%20%2B%20WinDivert-4f46e5)]()

</div>

---

## О проекте

**zapret-GUI-Windows** — графическая обёртка над Windows-версией zapret.
Вместо nfqws + nftables здесь работает **winws.exe** (Windows-сборка zapret) с
драйвером перехвата **WinDivert**. GUI не хранит свою логику обхода: он
разбирает те же `.bat`-стратегии Flowseal и запускает под ними winws-процессы.

> Linux-версия: [SkilinPur/zapret-GUI](https://github.com/SkilinPur/zapret-GUI)

## Статус проекта

В **активной разработке**. Собирается в `.exe` автоматически (GitHub Actions) —
забирайте свежую сборку в [Релизах](https://github.com/SkilinPur/zapret-GUI-Windows/releases).

## Что уже умеет

- **Запуск/остановка обхода** — парсинг нативных Flowseal-стратегий и запуск
  winws-процессов от администратора;
- **Способ обхода с авто-описанием** — человеческое объяснение каждого `.bat`;
- **Обновление компонентов** — ядро (winws + WinDivert) и стратегии Flowseal
  скачиваются из пакета Flowseal;
- **Тёмная тема и трей**;
- **Автозапуск** — планировщик задач (при входе пользователя).

В планах: мастер первого запуска, самопроверка «работает ли», самообновление
программы, подпись/установщик. Подробный план — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Как это устроено

```
┌──────────────┐     ┌──────────────────────────┐
│  zapret-GUI  │ ──▶ │ winws.exe (Windows zapret)│
│  (PySide6)   │     │  + WinDivert (драйвер)    │
└──────────────┘     └──────────────────────────┘
  стратегии: Flowseal (.bat, списки, шаблоны) — нативные, под winws
```

- **Движок** — `winws.exe` + `WinDivert64.sys`/`WinDivert.dll` (из пакета Flowseal).
- **Стратегии** — нативные `.bat` из [Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).
- **Права** — приложение запускается от имени администратора (UAC), драйвер
  WinDivert поднимается автоматически при старте winws.
- **Автозапуск** — задача планировщика Windows «Zapret-GUI».

## Установка и запуск

1. Скачайте **`zapret-GUI-Windows.zip`** из [Релизов](https://github.com/SkilinPur/zapret-GUI-Windows/releases).
2. Распакуйте архив в любую папку (например `C:\zapret\`).
3. Запустите **`ZapretGUI.exe`** (папка `ZapretGUI`).
4. Если Windows предупреждает о неизвестном издателе — «Подробнее» →
   «Выполнить в любом случае» (сборки не подписаны).
5. Подтвердите запрос UAC (нужны права администратора).

**Первый запуск:**
- вкладка **«Обновление»** → «Скачать/обновить ядро» и «Скачать/обновить стратегии»;
- вкладка **«Способ обхода»** → выбрать, «Применить»;
- вкладка **«Статус»** → «Включить обход».

> Кнопка «Закрыть» сворачивает окно в трей; завершить программу — из трея.

## Сборка из исходников / CI

```bash
git clone https://github.com/SkilinPur/zapret-GUI-Windows.git
cd zapret-GUI-Windows
pip install -r gui/requirements.txt
python -m gui.app.main          # запуск из исходников (mock-бэкенд на Linux)
python -m PyInstaller gui.spec  # сборка .exe (Windows)
```

Сборка в `.exe` выполняется в GitHub Actions (`windows-latest`): импорт-проверки,
PyInstaller (`onedir`, запуск от администратора), zip-артефакт, публикация в
релиз по тегу `v*`.

## Требования

- Windows 10/11 **x64**
- Права администратора (UAC)

## Авторство

| Роль | Автор | Репозиторий |
|---|---|---|
| GUI (этот проект) | [SkilinPur](https://github.com/SkilinPur) | [zapret-GUI-Windows](https://github.com/SkilinPur/zapret-GUI-Windows) |
| Ядро/winws | [bol-van](https://github.com/bol-van) | [zapret](https://github.com/bol-van/zapret) |
| Стратегии/пакет winws | [Flowseal](https://github.com/Flowseal) | [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube) |
| GUI-концепт (Linux) | [SkilinPur](https://github.com/SkilinPur) | [zapret-GUI](https://github.com/SkilinPur/zapret-GUI) |

## Лицензия и предупреждение

Лицензионные условия наследуются от исходных проектов
([zapret](https://github.com/bol-van/zapret),
[zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube)).

Программа предназначена для обхода технических ограничений и замедлений
в странах, где это разрешено законом. Используйте её ответственно — соблюдайте
законодательство вашей юрисдикции.
