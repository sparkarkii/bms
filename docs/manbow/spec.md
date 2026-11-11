# bms — Specification

Status: draft · Last updated: 2026-11-03

"bms" is a repository for BMS (short for [Be-Music Sources](https://en.wikipedia.org/wiki/Be-Music_Source)) related stuff. The manbow directory inside contains utilities to download BMS songs from [this website](https://manbow.nothing.sh/event/event.cgi), so the user can play them via emulators like beatoraja.
This document covers what the manbow scripts must do, how it is structured, the data it passes around, and how it is tested.

---

## 1. Requirements

### 1.1 Functional

| ID | Requirement |
|----|-------------|
| R1 | Given an event and an optional range of entries, the scripts should download those BMS songs to the specified output directory. |
| R2 | After downloads complete, the archives should be extracted. |
| R3 | BMS files should be well-orgainzed on the local storage. (see 3.3)|
| R4 | Always show the progress clearly so the user know what's going on. |
| R5 | If there is an issue of a single shared link (e.g., not available anymore), skip to the next. Only problems that affect whole downloads (e.g., network down, running out of disk space) may stop it. |
| R6 | Japanese filenames must show correctly, not garbled. |
| R7 | There should be a list containing songs that has multiple shared links after each run, so the user can decide which format (e.g., OGG or WAV) to keep. |  
| R8 | There should be a list containing songs that has an attachment file after each run, so the user can sort the files. |
| R9 | There should be a list containing songs unavailable or failed to download after each run, so the user can know which directory is empty. | 
| R10 | The manbow website has two page layout: with a `Team` table column (`No, Name, Team, Title, Size, Addr`) and without one (`No, Name, Title, Size, Addr`). The scripts should support both. |
| R11 | Since Google drive and Dropbox files appear more frequently than others, the scripts should support both of them. | 
| R12 | The user will have to download the songs the script failed to download manually. We should simplify this process if possible. |
| R13 | The scripts should verify the download and extraction output. |
| R14 | If the run stops partway, the failure (R7-R9) found so far must not be lost. |
| R15 | After each run, show a summary includes how many songs succeeded, how many failed, and how many links each file host had. |
| R16 | Rerun on the same output directory must not overwrite the failure lists (R7-R9), instead it should update the information. |

### 1.2 Non-functional

| ID | Requirement |
|----|-------------|
| N1 | Python only (≥ 3.14), managed with "uv". |
| N2 | Works on Linux: file names and paths should be handled correctly. |
| N3 | Every new feature or fixes should be covered by automated unit tests. |
| N4 | Each download or extraction bug gets a test before it is fixed. |

---

## 2. Plan

The manbow scripts are split into three commands, run in this order:
1. **downloadall** downloads and extracts every song it can, without any help from the user. Links that fail are recorded in failed.json (see 3.3 and 4. Data models).
2. **resolve** opens each failed link in a browser. The user clicks through to the download, and the real download URL is recorded in failed.json.
3. **retry** downloads and extracts the links that resolve found.


**Downloadall**
S1: Fetch the page
- How: call requests.get() with event, start and end, plus a timeout, then raise_for_status().
- Fulfills: R1
- Module: site.py
- If it fails: stop with a clear error.

S2: Read the page
- How: check the charset in the raw bytes, decode as cp932 with errors='replace', then parse with BeautifulSoup and html5lib.
- Fulfills: R1, R6
- Module: site.py
- If it fails: if the charset isn't Shift_JIS, stop with a clear error.

S3: Detect the layout
- How: match the <th> texts to a Layout value.
- Fulfills: R10
- Module: site.py
- If it fails: if the headers are missing or unknown, stop and show what was found.

| R3 | Given an event ID and an optional "start"/"end" range, fetch that event's HTML page and parse it into usable data. It should support two different webpage layouts, and any unknown layout will stop the run with a clear error. |
| R4 | Create a folder structure under chosen output directory that is tidy enough for the user to organize (See 3.6). |
| R5 | Japanese filenames must survive extraction. They must be decoded correctly, not garbled. |
| R6 | Correctly recognize the file host and download Google Drive files, Google Drive folders, and Dropbox links. After every download, verify the file before extracting it: it is not empty, it is not an HTML page, and it should pass an archive integrity test. Those failures will be recorded (see R8). |
| R7 | Extract verified archives in place then delete the archive. Also verify the output and record the failure (see R8). |
| R8 | Any link that fails (unsupported host, download error, verification error, extraction error) is recorded in `failed.json` with the reason. |

**Resolve**:
| R9 | open each failed link in a real browser, let the user click through to the download, and record the real (direct) download URL in `failed.json`. Re-running it continues where it stopped. |

**Retry**:
| R10 | download every resolved link from `failed.json` into its track directory, using the same verify/extract rules as R6–R7. Re-running it continues where it stopped. |
| R11 | Tracks (A track is a table row) with multiple downloadable links should be recorded to inform the user. We'll do this by exporting a `multilink.json` with description (e.g. "本体", "BGA") contains in it after downloadall finishes. |
| R12 | After downloadall finishes, write `attachment.json`: every downloaded file that is not an archive, so it can be checked by hand. |


* A step below is the smallest action that can be tested on its own and still makes sense when describing the run.
* See 3.2 for module information.

---

## 3. Architecture

### 3.1 Libraries

| Library |
|---------|
| requests | 
| beautifulsoup4 + html5lib | 
| gdown | 
| patool | 
| playwright | 
| **typer** (new) |
| **pydantic** (new) | 

### 3.2 Module layout

```
src/bms/
  cli.py                  
  manbow/
    models.py             
    site.py               # requests, beautifulsoup4, html5lib / event_id, start, end
    filesys.py            # / save_to
    download.py           # gdown
    extract.py            # patool
    report.py             # pydantic
    browser.py            # playwright
    commands/
      downloadall.py
      resolve.py
      retry.py
tests/
```

### 3.3 Output files

Everything is written into `save_to`:

```
<save_to>/
  001. <Title> (by <Artists>)/   # one directory per track
  002. ...
  failed.json                    # failed links; updated by resolve and retry
  multilink.json                 # tracks with more than one link
  attachment.json                # downloaded files that are not archives
  log.txt                        # unexpected errors
```

### 3.4 CLI

`pyproject.toml`: `bms = "bms.cli:app"`

```
bms manbow downloadall  <event> <output_dir> [--start N] [--end N]
bms manbow resolve <output_dir>
bms manbow retry   <output_dir>
```

---

## 4. Data models

```python
class Layout(Enum):              # replaces the "has_team" / "doesn't_have_team" strings
    WITH_TEAM = "with_team"
    WITHOUT_TEAM = "without_team"

@dataclass
class Track:
    event: str
    num: str
    artists: str
    team: str | None
    title: str
    size: str
    urls: list[str]
    addr_text: str

class Outcome(Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"      # no downloader for this host
    DOWNLOAD_ERROR = "download_error"
    INVALID_FILE = "invalid_file"    # failed verification (HTML page, empty, corrupt)
    EXTRACT_ERROR = "extract_error"

@dataclass
class DownloadResult:            # replaces Path | list[Path] | Exception | None
    outcome: Outcome
    files: list[Path]
    error: str | None = None

class Stage(Enum):
    FAILED = "failed"            # written by downloadall
    RESOLVED = "resolved"        # direct_url found by resolve
    DOWNLOADED = "downloaded"    # finished by retry

class FailedLink(BaseModel):     # one record in failed.json
    event: str
    track_num: str
    track_dir: Path
    link: Link
    reason: Outcome
    error: str | None = None
    stage: Stage = Stage.FAILED
    direct_url: str | None = None
    filename: str | None = None
```

`failed.json` is a JSON list of `FailedLink`. `report.py` is the only module that
reads or writes it, and it saves the whole file after each change so an
interrupted step can be resumed.

---

## 4. Testing strategy

### 4.1 Layers

| Layer | What it tests | Network | Runs in CI |
|-------|---------------|---------|------------|
| **Unit** | scraper (both layouts), directory naming, URL dispatch, `report` read/write, the logic that updates `failed.json` in resolve/retry | No | Yes |
| **Archive** | `verify` + `extract` against a set of real archive files (§5.2) | No | Yes |
| **Wrapper** | gdown wrappers with gdown replaced by a fake (`monkeypatch`) that reproduces each known failure | No | Yes |
| **Live** | real downloads from test links we own on Google Drive and Dropbox | Yes | No — run by hand |

The playwright browser itself is not tested automatically (it needs a human);
only the logic around it is.

### 4.2 Fixtures

```
tests/fixtures/
  pages/          # saved manbow URLList pages: one per layout
  archives/       # small sample files:
                  #   ok.zip, ok.rar, ok.7z
                  #   sjis_names.zip        (Shift_JIS filenames, R8)
                  #   truncated.zip         (corrupt)
                  #   html_as.zip           (HTML error page with a .zip name)
                  #   empty.zip             (0 bytes)
                  #   nested.zip            (archive inside an archive)
                  #   not_archive.txt
```

Test links for the live tests (on accounts we own, so they don't disappear): a
small Drive file, a Drive folder, a Drive file over 100 MB (triggers Google's
virus-scan warning page), and a Dropbox file.

### 4.3 Rules

- Every real bug in download or extraction gets saved as a fixture and a failing
  test **before** it is fixed.
- Live tests are marked `@pytest.mark.live` and skipped by default
  (`addopts = "-m 'not live'"`); run them with `uv run pytest -m live`.
- Before upgrading gdown or patool: run the wrapper, archive and live tests.
- No code that is under test calls `os.get_terminal_size()` or prints directly;
  terminal output goes through one place (rich), so tests and CI don't crash
  without a terminal.

### 4.4 CI

GitHub Actions, on every push and pull request:

1. Install `uv`, then `7zip` and `unrar` via apt.
2. `uv run ruff check` and `uv run ruff format --check`.
3. `uv run pytest` (everything except live tests).

---

## 5. Risks and open questions

- **Shift_JIS filenames (R8).** Not seen yet, but very likely. Python's
  `zipfile` can decode them (`metadata_encoding="cp932"`); whether patool's
  system tools can is to be found out by the archive tests.
- **Google rate limits.** Large events may hit Drive download quotas; these show
  up as HTML pages (caught by R6) and end up in `failed.json`.
- **Auto-download after resolve.** Currently a separate retry step (D3). May be
  merged into resolve later.
- **One review file or two?** `multilink.json` and `attachment.json` could be
  merged into one file of "tracks to check by hand" with a `reason` per entry.
- **Nested folders after extraction** (`_handle_filedepth` to-do): how deep
  should the song files end up? Not decided.

---

## 6. Suggested order of work

1. Add ruff, pytest; fix the current breakages (`models.py` import, undefined
   `row_data`). Set up CI.
2. Data models + `report.py` (pydantic).
3. Split `scraper.py` out of `Task`; unit tests with saved pages.
4. `verify.py` + `extract.py`; archive fixtures and tests.
5. Downloader wrappers + wrapper tests; live test links.
6. `pipeline.py` + typer CLI; rich output.
7. Resolve step (from `manually.py`), then retry step.
