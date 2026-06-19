# ExamGuard 🛡

A lab exam monitoring desktop application built with Python + CustomTkinter.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
python main.py
```

## Features

### Student View
- Enter name and student ID before starting
- Large countdown-up timer (hh:mm:ss)
- "End Exam" button unlocks after 10 seconds
- Prevents window close during active exam
- "Exam Ended" thank-you overlay on completion

### Monitoring Engine (runs silently)
| Monitor | What it captures | Interval |
|---------|-----------------|----------|
| Window Switch | Active window title changes | Every 0.5s |
| Clipboard | Clipboard content changes (first 100 chars) | Every 1s |
| Screenshots | Full screen PNG saved to `screenshots/` | Every 2 minutes |
| Keystrokes | Running total + backspace count | Saved every 30s |

### Instructor Dashboard
- Protected by PIN (default: `1234`)
- Session table with color-coded **Risk Score**:
  - 🟢 Green: 0–10
  - 🟡 Yellow: 11–25
  - 🔴 Red: 26+
- Risk formula: `(window_switches × 2) + (clipboard_events × 5)`
- Full scrollable event timeline per student
- Click screenshot events to open the image
- Export individual session as CSV
- Clear sessions older than 30 days

## File Structure

```
ExamGuard/
├── main.py              # Entry point, role selector
├── student_app.py       # Student exam interface
├── instructor_app.py    # Instructor dashboard
├── monitor.py           # Background monitoring engine
├── database.py          # SQLite CRUD operations
├── config.py            # PIN, intervals, thresholds
├── requirements.txt     # Python dependencies
├── examguard.db         # Auto-created on first run
└── screenshots/         # Auto-created for screenshots
```

## Configuration (config.py)

| Setting | Default | Description |
|---------|---------|-------------|
| `INSTRUCTOR_PIN` | `"1234"` | Instructor dashboard PIN |
| `SCREENSHOT_INTERVAL` | `120` | Seconds between screenshots |
| `WINDOW_CHECK_INTERVAL` | `0.5` | Window poll frequency |
| `CLIPBOARD_CHECK_INTERVAL` | `1.0` | Clipboard poll frequency |
| `MIN_EXAM_SECONDS` | `10` | Seconds before End Exam unlocks |

## Requirements
- Python 3.10+
- Windows (for pygetwindow & ImageGrab screenshot support)
- Packages: `customtkinter`, `pillow`, `pynput`, `pyperclip`, `pygetwindow`
