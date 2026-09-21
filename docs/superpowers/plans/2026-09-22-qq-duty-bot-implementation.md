# QQ Duty Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Windows desktop program that manages an extendable duty roster and automatically @mentions tomorrow's assigned member in one QQ group through NapCat OneBot HTTP.

**Architecture:** Keep scheduling and business rules independent from Tkinter and HTTP. Pure roster/persistence functions feed a `ReminderService`; a small `NapCatClient` owns OneBot calls; the GUI delegates network work to a background executor and receives results through a queue. `QQBot.py` is a thin GUI/CLI entry point.

**Tech Stack:** Python 3.10+, standard-library Tkinter, `requests`, `schedule`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-22-qq-duty-bot-design.md`

## Global Constraints

- Windows is the target platform.
- Robot QQ is `3851479069`; default group is `1094289617`; default send time is `20:00`.
- Never start or stop QQ or NapCat from the application.
- Never persist or log the NapCat token.
- Automated tests must never contact the real OneBot endpoint.
- A duty date is recorded only after OneBot returns `retcode = 0`.
- Real sending is not part of implementation verification unless the user explicitly requests it.

## Review Focus

- A corrupt JSON file must produce a useful error and must not be overwritten.
- Duplicate dates must be rejected before any roster save.
- A logged-in QQ other than `3851479069` must block sending.
- A timeout or OneBot error must not mark the date as sent.
- Closing the GUI while automatic scheduling is active must warn that reminders will stop.

---

### Task 1: Roster model and atomic JSON persistence

**Files:**
- Create: `qqbot/__init__.py`
- Create: `qqbot/models.py`
- Create: `qqbot/storage.py`
- Create: `tests/test_storage.py`
- Create: `roster.json`
- Create: `settings.json`
- Create: `sent_reminders.json`

**Interfaces:**
- Produces: `DutyEntry`, `Settings`, `load_roster(path)`, `save_roster(path, entries)`, `load_settings(path)`, `load_sent_dates(path)`, `save_sent_dates(path, dates)`, `next_workday(day)`.

- [ ] **Step 1: Write failing model and storage tests**

```python
def test_save_roster_sorts_by_date_and_round_trips(tmp_path):
    path = tmp_path / "roster.json"
    entries = [DutyEntry(date(2026, 9, 24), 1, "乙"), DutyEntry(date(2026, 9, 23), 2, "甲")]
    save_roster(path, entries)
    assert [x.duty_date.isoformat() for x in load_roster(path)] == ["2026-09-23", "2026-09-24"]

def test_duplicate_duty_date_is_rejected(tmp_path):
    path = tmp_path / "roster.json"
    entries = [DutyEntry(date(2026, 9, 23), 1, "甲"), DutyEntry(date(2026, 9, 23), 2, "乙")]
    with pytest.raises(ValueError, match="重复日期"):
        save_roster(path, entries)

def test_invalid_qq_and_blank_name_are_rejected():
    with pytest.raises(ValueError):
        DutyEntry(date(2026, 9, 23), 0, "甲")
    with pytest.raises(ValueError):
        DutyEntry(date(2026, 9, 23), 1, " ")

def test_corrupt_json_is_not_overwritten(tmp_path):
    path = tmp_path / "roster.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="无法读取"):
        load_roster(path)
    assert path.read_text(encoding="utf-8") == "{broken"

def test_next_workday_skips_weekend():
    assert next_workday(date(2026, 9, 25)) == date(2026, 9, 28)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_storage.py -v`

Expected: collection fails because `qqbot.models` and `qqbot.storage` do not exist.

- [ ] **Step 3: Implement validated dataclasses and atomic persistence**

Implement immutable `DutyEntry`, validated `Settings`, ISO date conversion, duplicate detection, UTF-8 JSON reading, and `tempfile.NamedTemporaryFile(delete=False, dir=path.parent)` followed by `Path.replace`. Implement `next_workday` by advancing at least one day while `weekday() >= 5`.

- [ ] **Step 4: Seed application data**

Populate `roster.json` from the confirmed 2026 Word roster, including at minimum the already verified mappings for 2026-09-23 and later dates. Create settings with the exact defaults in the spec and an empty JSON array for sent reminders. Do not include a token.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m pytest tests/test_storage.py -v`

Expected: all storage tests pass with no warnings.

- [ ] **Step 6: Commit**

```bash
git add qqbot roster.json settings.json sent_reminders.json tests/test_storage.py
git commit -m "feat: add validated duty roster storage"
```

### Task 2: NapCat configuration and OneBot client

**Files:**
- Create: `qqbot/napcat.py`
- Create: `tests/test_napcat.py`

**Interfaces:**
- Consumes: `Settings` from Task 1.
- Produces: `NapCatEndpoint`, `NapCatClient.get_login_info()`, `NapCatClient.get_group_member_info(group_id, user_id)`, `NapCatClient.send_group_reminder(group_id, user_id)`, `build_reminder_segments(user_id)`.

- [ ] **Step 1: Write failing endpoint and message tests**

```python
def test_load_endpoint_uses_enabled_http_server_without_exposing_token(tmp_path):
    path = tmp_path / "onebot.json"
    path.write_text(json.dumps({"network": {"httpServers": [{"enable": True, "host": "127.0.0.1", "port": 3002, "token": "secret"}]}}), encoding="utf-8")
    endpoint = NapCatEndpoint.from_config(path)
    assert endpoint.base_url == "http://127.0.0.1:3002"
    assert "secret" not in repr(endpoint)

def test_message_has_true_at_segment():
    assert build_reminder_segments(3060569778) == [
        {"type": "at", "data": {"qq": "3060569778"}},
        {"type": "text", "data": {"text": "，明天轮到你值班，祝你工作顺利"}},
    ]

def test_nonzero_retcode_raises_without_token_in_error(fake_session):
    fake_session.response = {"retcode": 100, "message": "failed"}
    client = NapCatClient(NapCatEndpoint("http://127.0.0.1:3002", "secret"), session=fake_session)
    with pytest.raises(NapCatError, match="retcode=100") as error:
        client.get_login_info()
    assert "secret" not in str(error.value)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_napcat.py -v`

Expected: collection fails because `qqbot.napcat` does not exist.

- [ ] **Step 3: Implement the client**

Read only the first enabled HTTP server, normalize `0.0.0.0` and `::` to `127.0.0.1`, require a valid port, set `Authorization: Bearer <token>`, use a 10-second timeout, and centralize response validation. Never include headers or endpoint token in exceptions or repr output.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_napcat.py -v`

Expected: all NapCat tests pass without network access.

- [ ] **Step 5: Commit**

```bash
git add qqbot/napcat.py tests/test_napcat.py
git commit -m "feat: add secure NapCat OneBot client"
```

### Task 3: Reminder service and duplicate protection

**Files:**
- Create: `qqbot/service.py`
- Create: `tests/test_service.py`

**Interfaces:**
- Consumes: storage interfaces from Task 1 and `NapCatClient` from Task 2.
- Produces: `ReminderResult`, `ReminderService.preview(duty_date)`, `ReminderService.send(duty_date, force=False)`.

- [ ] **Step 1: Write failing service tests**

```python
def test_missing_date_returns_skipped(service):
    result = service.send(date(2026, 9, 27))
    assert result.status == "skipped"
    assert "没有排班" in result.message

def test_duplicate_is_blocked_without_calling_client(service, client):
    service.sent_dates.add("2026-09-23")
    result = service.send(date(2026, 9, 23))
    assert result.status == "skipped"
    assert client.calls == []

def test_force_bypasses_duplicate_guard(service, client):
    service.sent_dates.add("2026-09-23")
    assert service.send(date(2026, 9, 23), force=True).status == "sent"

def test_wrong_logged_in_account_blocks_send_and_does_not_record(service, client):
    client.login_qq = 123
    result = service.send(date(2026, 9, 23))
    assert result.status == "error"
    assert "3851479069" in result.message
    assert "2026-09-23" not in service.sent_dates

def test_failed_send_is_not_recorded(service, client):
    client.send_error = NapCatError("failed")
    assert service.send(date(2026, 9, 23)).status == "error"
    assert "2026-09-23" not in service.sent_dates

def test_success_records_date_after_member_check(service, client):
    result = service.send(date(2026, 9, 23))
    assert result.status == "sent"
    assert client.calls == ["login", "member:1094289617:3060569778", "send:1094289617:3060569778"]
    assert "2026-09-23" in service.sent_dates
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_service.py -v`

Expected: collection fails because `ReminderService` does not exist.

- [ ] **Step 3: Implement minimal reminder orchestration**

Return structured results instead of printing. Verify login QQ, member presence and send result in order. Call the injected persistence function only after success. Preview must never construct or call a NapCat client.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m pytest tests/test_service.py -v`

Expected: all service tests pass.

- [ ] **Step 5: Commit**

```bash
git add qqbot/service.py tests/test_service.py
git commit -m "feat: add reminder rotation and duplicate protection"
```

### Task 4: Tkinter window and scheduler controller

**Files:**
- Create: `qqbot/gui.py`
- Create: `qqbot/scheduler.py`
- Create: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `DutyEntry`, storage functions and `ReminderService`.
- Produces: `SchedulerController.start()`, `SchedulerController.stop()`, `SchedulerController.run_pending()`, `DutyBotWindow`.

- [ ] **Step 1: Write failing scheduler tests**

```python
def test_scheduler_registers_daily_local_time(fake_schedule):
    controller = SchedulerController("20:00", lambda: None, schedule_module=fake_schedule)
    controller.start()
    assert fake_schedule.registered_time == "20:00"

def test_stop_clears_only_its_own_job(fake_schedule):
    controller = SchedulerController("20:00", lambda: None, schedule_module=fake_schedule)
    controller.start()
    controller.stop()
    assert fake_schedule.cancelled == [controller.job]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_scheduler.py -v`

Expected: collection fails because `SchedulerController` does not exist.

- [ ] **Step 3: Implement scheduler and GUI**

The scheduler owns exactly one daily job and never spawns QQ. The GUI uses `ttk.Treeview` for roster rows, validated dialogs for add/edit, confirmation dialogs for delete/force resend/exit, a `ThreadPoolExecutor(max_workers=1)` for network work, and `queue.Queue` plus `root.after(100, drain_queue)` for main-thread updates. The automatic callback sends `date.today() + timedelta(days=1)`.

- [ ] **Step 4: Add GUI validation helpers and test them as pure functions**

Add tests for duplicate date detection, numeric QQ validation, blank name rejection and next-workday calculation. Keep widget layout itself out of brittle screenshot tests.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m pytest tests/test_scheduler.py tests/test_storage.py -v`

Expected: all scheduler and validation tests pass.

- [ ] **Step 6: Commit**

```bash
git add qqbot/gui.py qqbot/scheduler.py tests/test_scheduler.py
git commit -m "feat: add roster editor and scheduled reminder window"
```

### Task 5: Entry point, Windows launcher and documentation

**Files:**
- Create: `QQBot.py`
- Create: `启动值班机器人.bat`
- Modify: `README.md`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces: `main(argv=None) -> int` supporting GUI, `--dry-run`, `--send-now`, and `--force`.

- [ ] **Step 1: Write failing CLI tests**

```python
def test_dry_run_prints_target_without_creating_client(app_factory, capsys):
    code = main(["--dry-run"], app_factory=app_factory)
    assert code == 0
    assert "郭子旋" in capsys.readouterr().out
    assert app_factory.client_created is False

def test_force_requires_send_now(capsys):
    assert main(["--force"]) != 0
    assert "--force 只能和 --send-now 一起使用" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_cli.py -v`

Expected: import or behavior failure because the entry point is not implemented.

- [ ] **Step 3: Implement CLI and launcher**

Use `argparse`; default to the GUI. Resolve data files relative to the script directory so double-click launch is stable. The batch file changes to `%~dp0`, verifies `python` exists, runs `python QQBot.py`, and pauses only on nonzero exit.

- [ ] **Step 4: Document exact setup and operation**

README must include Python installation, `pip install -r requirements.txt`, NapCat command-line startup, first GUI launch, continuing the roster, automatic reminder requirements, immediate send, dry-run, error explanations, and the warning that closing either NapCat or the GUI stops reminders.

- [ ] **Step 5: Run the full automated suite**

Run: `python -m pytest -v`

Expected: all tests pass; no test accesses `127.0.0.1:3002`.

- [ ] **Step 6: Run syntax and dry-run verification**

Run: `python -m compileall QQBot.py qqbot`

Expected: exit code 0.

Run: `python QQBot.py --dry-run`

Expected: prints tomorrow's roster status without sending a QQ message.

- [ ] **Step 7: Commit**

```bash
git add QQBot.py "启动值班机器人.bat" README.md requirements.txt requirements-dev.txt tests/test_cli.py
git commit -m "feat: ship Windows QQ duty reminder app"
```

### Task 6: Final integration verification and GitHub handoff

**Files:**
- Verify all tracked project files.

**Interfaces:**
- Consumes: complete application.
- Produces: a tested commit ready for `cong241/FZUREABOT`.

- [ ] **Step 1: Verify repository contents and secrets**

Run: `git status --short`

Expected: only intentional files are present.

Run: `rg -n "Bearer |ACCESS_TOKEN|token\s*[=:]\s*['\"]" -g '!tests/**' .`

Expected: no literal credential is committed; runtime configuration-reading code is allowed but no token value appears.

- [ ] **Step 2: Re-run all tests from a clean process**

Run: `python -m pytest -v`

Expected: all tests pass with zero failures.

- [ ] **Step 3: Verify the real local configuration read without sending**

Run: `python QQBot.py --dry-run`

Expected: valid roster preview; no `send_group_msg` request.

- [ ] **Step 4: Review commit history and push only after authorization**

Run: `git log --oneline --decorate -6`

Expected: focused implementation commits on top of the repository's initial commit. Push to `https://github.com/cong241/FZUREABOT` only after confirming GitHub authentication and the user's authorization remains current.
