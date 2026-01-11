#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Mutex, OnceLock};

use tauri::{AppHandle, Emitter};

struct SidecarRuntime {
    child: Child,
    stdin: ChildStdin,
}

static SIDECAR: OnceLock<Mutex<Option<SidecarRuntime>>> = OnceLock::new();

#[tauri::command]
fn run_sidecar_job(app: AppHandle, message: String) -> Result<(), String> {
    send_message(&app, &message)
}

fn start_sidecar(app: &AppHandle) -> Result<SidecarRuntime, String> {
    let root = resolve_root()?;
    let sidecar_path = root.join("sidecar").join("main.py");
    if !sidecar_path.exists() {
        return Err(format!("sidecar not found: {}", sidecar_path.display()));
    }

    let python = resolve_python(&root);
    let mut child = Command::new(&python)
        .arg(&sidecar_path)
        .current_dir(&root)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| format!("failed to spawn sidecar: {err}"))?;

    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "failed to open sidecar stdin".to_string())?;

    if let Some(stderr) = child.stderr.take() {
        let app_handle = app.clone();
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().flatten() {
                let _ = app_handle.emit("sidecar-log", line);
            }
        });
    }

    if let Some(stdout) = child.stdout.take() {
        let reader = BufReader::new(stdout);
        let app_handle = app.clone();
        std::thread::spawn(move || {
            for line in reader.lines().flatten() {
                let _ = app_handle.emit("sidecar-message", line);
            }
        });
    }

    Ok(SidecarRuntime { child, stdin })
}

fn send_message(app: &AppHandle, message: &str) -> Result<(), String> {
    let holder = SIDECAR.get_or_init(|| Mutex::new(None));
    let mut guard = holder.lock().map_err(|_| "sidecar lock poisoned".to_string())?;

    if let Some(runtime) = guard.as_mut() {
        if let Ok(Some(status)) = runtime.child.try_wait() {
            let _ = app.emit("sidecar-log", format!("sidecar exit: {status}"));
            *guard = None;
        }
    }

    if guard.is_none() {
        *guard = Some(start_sidecar(app)?);
    }

    if let Some(runtime) = guard.as_mut() {
        runtime
            .stdin
            .write_all(message.as_bytes())
            .and_then(|_| runtime.stdin.write_all(b"\n"))
            .and_then(|_| runtime.stdin.flush())
            .map_err(|err| format!("failed to write to sidecar: {err}"))?;
    }
    Ok(())
}

fn resolve_python(root: &PathBuf) -> PathBuf {
    if let Ok(custom) = std::env::var("NAI_PYTHON") {
        return PathBuf::from(custom);
    }
    let venv_python = root.join("venv").join("Scripts").join("python.exe");
    if venv_python.exists() {
        return venv_python;
    }
    PathBuf::from("python")
}

fn resolve_root() -> Result<PathBuf, String> {
    if let Ok(root) = std::env::var("NAI_ROOT") {
        return Ok(PathBuf::from(root));
    }
    let mut dir = std::env::current_dir().map_err(|err| err.to_string())?;
    for _ in 0..5 {
        if dir.join("sidecar").exists() {
            return Ok(dir);
        }
        if !dir.pop() {
            break;
        }
    }
    Err("cannot resolve project root (set NAI_ROOT)".to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![run_sidecar_job])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
