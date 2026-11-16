// SPDX-License-Identifier: Apache-2.0
//! Public refresh configuration and startup behavior.

use std::sync::Arc;
use std::time::Duration;

use clap::Parser;
use git_cache_proxy::config::Config;
use git_cache_proxy::git::{GitCache, GitConfig};
use git_cache_proxy::metrics::Metrics;

#[tokio::test(start_paused = true)]
async fn refresh_default_disabled_does_not_start_a_task() {
    let cfg = Config::try_parse_from(["proxy", "--upstream", "https://example.com"]).unwrap();
    assert_eq!(cfg.refresh_interval_seconds, 0);
    assert_eq!(cfg.refresh_active_window_seconds, 604800);
    assert_eq!(cfg.max_concurrent_refreshes, 4);
    cfg.validate_refresh().unwrap();
    let cache = GitCache::new(
        GitConfig {
            git_binary: "missing-git-must-not-run".into(),
            upstream_auth_header: None,
            big_file_threshold: "8m".into(),
            fetch_ttl: Duration::from_secs(10),
            max_wants: 100,
            max_upload_packs: 0,
            pack_threads: None,
            pack_window_memory: None,
        },
        Arc::new(Metrics::new()),
        None,
    );
    assert!(
        cache
            .start_refresh(
                Duration::from_secs(cfg.refresh_interval_seconds),
                Duration::from_secs(cfg.refresh_active_window_seconds),
                cfg.max_concurrent_refreshes,
            )
            .is_none()
    );
    tokio::time::advance(Duration::from_secs(604800)).await;
    cache.shutdown();
    cache.wait_for_shutdown().await;
}

#[test]
fn refresh_validation_ignores_inactive_options_when_disabled() {
    let mut cfg = Config::try_parse_from([
        "proxy",
        "--upstream",
        "https://example.com",
        "--max-concurrent-refreshes",
        "0",
    ])
    .unwrap();
    assert!(cfg.validate_refresh().is_ok());
    cfg.refresh_interval_seconds = 3599;
    assert!(cfg.validate_refresh().is_err());
    cfg.refresh_interval_seconds = 3600;
    assert!(cfg.validate_refresh().is_err());
    cfg.max_concurrent_refreshes = 1;
    assert!(cfg.validate_refresh().is_ok());
}

#[test]
fn refresh_validation_rejects_overflow_and_zero_active_window() {
    let mut cfg = Config::try_parse_from(["proxy", "--upstream", "https://example.com"]).unwrap();
    cfg.refresh_interval_seconds = u64::MAX;
    assert!(
        cfg.validate_refresh()
            .unwrap_err()
            .to_string()
            .contains("monotonic deadline")
    );
    cfg.refresh_interval_seconds = 3600;
    cfg.refresh_active_window_seconds = 0;
    assert!(
        cfg.validate_refresh()
            .unwrap_err()
            .to_string()
            .contains("--refresh-active-window-seconds")
    );
    cfg.refresh_interval_seconds = 0;
    assert!(cfg.validate_refresh().is_ok());
}

#[test]
fn refresh_invalid_settings_fail_before_creating_cache() {
    for (interval, concurrency, diagnostic) in [
        ("3599", "4", "--refresh-interval-seconds"),
        ("18446744073709551615", "4", "monotonic deadline"),
        ("3600", "0", "--max-concurrent-refreshes"),
    ] {
        let root = tempfile::tempdir().unwrap();
        let cache = root.path().join("not-created");
        let output = std::process::Command::new(env!("CARGO_BIN_EXE_git-cache-proxy"))
            .args([
                "--upstream",
                "https://example.com",
                "--refresh-interval-seconds",
                interval,
                "--max-concurrent-refreshes",
                concurrency,
                "--cache-root",
            ])
            .arg(&cache)
            .output()
            .unwrap();
        assert!(!output.status.success());
        assert!(String::from_utf8_lossy(&output.stderr).contains(diagnostic));
        assert!(!cache.exists());
    }
}
