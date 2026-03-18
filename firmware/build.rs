fn main() {
    embuild::espidf::sysenv::output();

    // partitions.csv をビルド出力にコピー
    let out_dir = std::env::var("OUT_DIR").unwrap_or_default();
    if !out_dir.is_empty() {
        let src = std::path::Path::new("partitions.csv");
        let dst = std::path::Path::new(&out_dir).join("partitions.csv");
        if src.exists() && !dst.exists() {
            let _ = std::fs::copy(src, dst);
        }
    }
}
