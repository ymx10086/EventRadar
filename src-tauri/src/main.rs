use std::{
    net::TcpListener,
    process::Stdio,
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

use tauri::{
    webview::{NewWindowFeatures, NewWindowResponse},
    Emitter, Url, WebviewUrl, WebviewWindowBuilder, Wry,
};
use tauri_plugin_shell::{process::CommandChild, ShellExt};

fn available_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    drop(listener);
    Ok(port)
}

fn wait_for_health(port: u16) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(90);
    let url = format!("http://127.0.0.1:{port}/api/health");
    while Instant::now() < deadline {
        if let Ok(response) = std::process::Command::new("curl")
            .args(["-fsS", &url])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
        {
            if response.success() {
                return Ok(());
            }
        }
        thread::sleep(Duration::from_millis(500));
    }
    Err("EventRadar backend did not become healthy in time".to_string())
}

fn handle_new_window(url: Url, _features: NewWindowFeatures) -> NewWindowResponse<Wry> {
    let _ = open::that(url.as_str());
    NewWindowResponse::Deny
}

fn main() {
    let backend: Arc<Mutex<Option<CommandChild>>> = Arc::new(Mutex::new(None));
    let backend_for_setup = backend.clone();
    let backend_for_exit = backend.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let port = available_port()?;
            let window_url = format!("http://127.0.0.1:{port}/events.html");
            let window = WebviewWindowBuilder::new(
                app,
                "main",
                WebviewUrl::External(Url::parse(&window_url).map_err(|e| e.to_string())?),
            )
            .title("EventRadar")
            .inner_size(1320.0, 900.0)
            .resizable(true)
            .visible(false)
            .on_new_window(handle_new_window)
            .build()
            .map_err(|e| e.to_string())?;

            let (mut rx, child) = app
                .shell()
                .sidecar("eventradar-server")
                .map_err(|e| e.to_string())?
                .args(["--host", "127.0.0.1", "--port", &port.to_string()])
                .spawn()
                .map_err(|e| format!("failed to start EventRadar backend: {e}"))?;

            thread::spawn(move || {
                while let Some(event) = rx.blocking_recv() {
                    println!("[eventradar-server] {event:?}");
                }
            });

            *backend_for_setup.lock().unwrap() = Some(child);

            wait_for_health(port)?;
            window.show().map_err(|e| e.to_string())?;
            app_handle.emit("eventradar-ready", port).ok();
            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(child) = backend_for_exit.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running EventRadar desktop app");
}
