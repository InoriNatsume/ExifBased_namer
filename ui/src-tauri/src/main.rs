#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};

use tauri::{AppHandle, Emitter};

#[tauri::command]
fn run_sidecar_job(app: AppHandle, message: String) -> Result<(), String> {
    let app_handle = app.clone();
    std::thread::spawn(move || {
        if let Err(err) = spawn_and_stream(&app_handle, &message) {
            let _ = app_handle.emit("sidecar-log", err);
        }
    });
    Ok(())
}

fn spawn_and_stream(app: &AppHandle, message: &str) -> Result<(), String> {
    let root = resolve_root()?;
    let sidecar_path = root.join("sidecar").join("main.py");
    if !sidecar_path.exists() {
        return Err(format!("sidecar not found: {}", sidecar_path.display()));
    }

    let mut child = Command::new("python")
        .arg(&sidecar_path)
        .current_dir(&root)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|err| format!("failed to spawn sidecar: {err}"))?;

    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(message.as_bytes())
            .and_then(|_| stdin.write_all(b"\n"))
            .and_then(|_| stdin.flush())
            .map_err(|err| format!("failed to write to sidecar: {err}"))?;
    }

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
        for line in reader.lines().flatten() {
            let _ = app.emit("sidecar-message", line);
        }
    }

    let status = child
        .wait()
        .map_err(|err| format!("failed to wait for sidecar: {err}"))?;
    let _ = app.emit("sidecar-log", format!("sidecar exit: {status}"));
    Ok(())
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
        .invoke_handler(tauri::generate_handler![run_sidecar_job])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
