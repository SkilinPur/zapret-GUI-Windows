# zapret-GUI-Windows

**Графический интерфейс для обхода замедления YouTube и Discord на Windows.**

Linux-версия (прототип концепта): https://github.com/SkilinPur/zapret-GUI

Это Windows-порт GUI-концепта: вся PySide6-оболочка (вкладки, мастер первого
запуска, обновление модулей, тёмная тема, трей) + **новый бэкенд для Windows**:

- ядро — **winws.exe** (Windows-сборка zapret) + драйвер **WinDivert**;
- права — UAC-администратор (вместо sudo/NOPASSWD);
- автозапуск — планировщик задач (вместо systemd);
- обновления — winws/стратегии отдельными модулями;
- сборка — в один `.exe` (PyInstaller/Nuitka).

Стратегии — те же `.bat`-наборы (winws-стиль, от Flowseal).

**Статус: идёт проектирование. Код ещё не перенесён.**

Подробности: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
