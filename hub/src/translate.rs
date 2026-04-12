// Moji — リアルタイム翻訳パイプライン
// STT (Whisper) → 翻訳 (LLM) → TTS (espeak/piper)
//
// Hub の mixer と統合: 翻訳済み音声を出力チャンネルに流す。

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::{mpsc, Mutex};

// ---- Language ----

/// Supported languages for the Moji translation pipeline.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    Ja,
    En,
    Zh,
    Ko,
    Es,
    Fr,
}

impl Language {
    /// BCP-47 tag for STT/TTS engines.
    pub fn bcp47(&self) -> &'static str {
        match self {
            Self::Ja => "ja-JP",
            Self::En => "en-US",
            Self::Zh => "zh-CN",
            Self::Ko => "ko-KR",
            Self::Es => "es-ES",
            Self::Fr => "fr-FR",
        }
    }

    /// ISO 639-1 code (used by translation APIs).
    pub fn iso639(&self) -> &'static str {
        match self {
            Self::Ja => "ja",
            Self::En => "en",
            Self::Zh => "zh",
            Self::Ko => "ko",
            Self::Es => "es",
            Self::Fr => "fr",
        }
    }

    /// Human-readable name.
    pub fn display_name(&self) -> &'static str {
        match self {
            Self::Ja => "Japanese",
            Self::En => "English",
            Self::Zh => "Chinese",
            Self::Ko => "Korean",
            Self::Es => "Spanish",
            Self::Fr => "French",
        }
    }
}

// ---- Request / Response ----

/// A request to translate spoken audio from one language to another.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranslateRequest {
    /// Raw PCM audio (16-bit mono, 16 kHz).
    #[serde(skip)]
    pub audio_pcm: Vec<i16>,
    /// Source language.
    pub source_lang: Language,
    /// Target language.
    pub target_lang: Language,
    /// Optional session ID for caching / context.
    pub session_id: Option<String>,
}

/// Result of the translation pipeline.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranslateResponse {
    /// Recognized text in the source language.
    pub original_text: String,
    /// Translated text in the target language.
    pub translated_text: String,
    /// Synthesized speech as PCM (16-bit mono, 16 kHz). Empty if TTS is disabled.
    #[serde(skip)]
    pub audio_pcm: Vec<i16>,
    /// Total end-to-end latency in milliseconds.
    pub latency_ms: u64,
    /// Per-stage latency breakdown.
    pub stage_latency: StageLatency,
}

/// Per-stage latency breakdown in milliseconds.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct StageLatency {
    pub stt_ms: u64,
    pub translate_ms: u64,
    pub tts_ms: u64,
}

// ---- Backend Configurations ----

/// Speech-to-text backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum SttBackend {
    /// Local Whisper subprocess (whisper.cpp or faster-whisper).
    WhisperLocal {
        model_path: String,
        /// "tiny", "base", "small", "medium", "large-v3"
        model_size: String,
    },
    /// OpenAI Whisper API.
    WhisperApi {
        api_key: String,
        endpoint: String,
    },
    /// Browser Web Speech API (used when pipeline runs client-side).
    WebSpeech,
}

/// Translation backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum TranslateBackend {
    /// Local LLM (e.g. Qwen, NLLB via llama.cpp).
    LlmLocal {
        model_path: String,
        endpoint: String,
    },
    /// Google Translate API.
    GoogleApi { api_key: String },
    /// DeepL API.
    DeepL { api_key: String },
    /// Simple dictionary fallback.
    Dictionary,
}

/// Text-to-speech backend.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum TtsBackend {
    /// Piper TTS (local, fast).
    PiperLocal {
        model_path: String,
        /// Path to piper binary.
        binary_path: String,
    },
    /// espeak-ng (local, lightweight).
    EspeakLocal,
    /// Browser Web Speech API (client-side).
    WebSpeech,
}

// ---- LRU Translation Cache ----

/// Simple LRU cache for translated text to avoid redundant API calls.
struct TranslationCache {
    entries: HashMap<String, String>,
    order: Vec<String>,
    capacity: usize,
}

impl TranslationCache {
    fn new(capacity: usize) -> Self {
        Self {
            entries: HashMap::with_capacity(capacity),
            order: Vec::with_capacity(capacity),
            capacity,
        }
    }

    fn get(&mut self, key: &str) -> Option<&str> {
        if self.entries.contains_key(key) {
            // Move to end (most recently used)
            self.order.retain(|k| k != key);
            self.order.push(key.to_string());
            self.entries.get(key).map(|s| s.as_str())
        } else {
            None
        }
    }

    fn insert(&mut self, key: String, value: String) {
        if self.entries.len() >= self.capacity {
            // Evict oldest
            if let Some(oldest) = self.order.first().cloned() {
                self.entries.remove(&oldest);
                self.order.remove(0);
            }
        }
        self.order.push(key.clone());
        self.entries.insert(key, value);
    }

    fn cache_key(text: &str, from: Language, to: Language) -> String {
        format!("{}:{}:{}", from.iso639(), to.iso639(), text)
    }
}

// ---- Translation Pipeline ----

/// The main pipeline that chains STT -> Translation -> TTS.
pub struct TranslationPipeline {
    stt: SttBackend,
    translator: TranslateBackend,
    tts: TtsBackend,
    cache: Arc<Mutex<TranslationCache>>,
}

impl TranslationPipeline {
    /// Create a new pipeline with the given backends.
    pub fn new(stt: SttBackend, translator: TranslateBackend, tts: TtsBackend) -> Self {
        Self {
            stt,
            translator,
            tts,
            cache: Arc::new(Mutex::new(TranslationCache::new(100))),
        }
    }

    /// Create a default pipeline using local backends (for Pi 5 / Hub).
    pub fn default_local() -> Self {
        Self::new(
            SttBackend::WhisperLocal {
                model_path: "/opt/koe/models/whisper-base.bin".into(),
                model_size: "base".into(),
            },
            TranslateBackend::Dictionary,
            TtsBackend::EspeakLocal,
        )
    }

    /// Process a translation request end-to-end.
    pub async fn process(&self, req: TranslateRequest) -> Result<TranslateResponse, PipelineError> {
        let t_total = Instant::now();

        // Stage 1: STT
        let t_stt = Instant::now();
        let original_text = self.run_stt(&req.audio_pcm, req.source_lang).await?;
        let stt_ms = t_stt.elapsed().as_millis() as u64;

        if original_text.trim().is_empty() {
            return Err(PipelineError::EmptyInput);
        }

        // Stage 2: Translation (with cache)
        let t_translate = Instant::now();
        let translated_text = self
            .run_translate(&original_text, req.source_lang, req.target_lang)
            .await?;
        let translate_ms = t_translate.elapsed().as_millis() as u64;

        // Stage 3: TTS
        let t_tts = Instant::now();
        let audio_pcm = self.run_tts(&translated_text, req.target_lang).await?;
        let tts_ms = t_tts.elapsed().as_millis() as u64;

        let latency_ms = t_total.elapsed().as_millis() as u64;

        Ok(TranslateResponse {
            original_text,
            translated_text,
            audio_pcm,
            latency_ms,
            stage_latency: StageLatency {
                stt_ms,
                translate_ms,
                tts_ms,
            },
        })
    }

    /// STT stage: convert audio to text.
    async fn run_stt(
        &self,
        audio: &[i16],
        lang: Language,
    ) -> Result<String, PipelineError> {
        match &self.stt {
            SttBackend::WhisperLocal { model_path, model_size } => {
                // Write PCM to temp WAV, run whisper subprocess
                let wav_path = write_temp_wav(audio)?;
                let output = tokio::process::Command::new("whisper-cpp")
                    .args([
                        "--model", model_path,
                        "--language", lang.iso639(),
                        "--output-txt",
                        "--no-timestamps",
                        &wav_path,
                    ])
                    .output()
                    .await
                    .map_err(|e| PipelineError::SttError(format!("whisper spawn: {e}")))?;

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    return Err(PipelineError::SttError(format!(
                        "whisper failed ({}): {stderr}",
                        model_size
                    )));
                }

                let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
                // Clean up temp file
                let _ = tokio::fs::remove_file(&wav_path).await;
                Ok(text)
            }
            SttBackend::WhisperApi { api_key, endpoint } => {
                let wav_data = encode_wav(audio);
                let client = reqwest::Client::new();
                let part = reqwest::multipart::Part::bytes(wav_data)
                    .file_name("audio.wav")
                    .mime_str("audio/wav")
                    .unwrap();
                let form = reqwest::multipart::Form::new()
                    .text("model", "whisper-1")
                    .text("language", lang.iso639().to_string())
                    .part("file", part);

                let resp = client
                    .post(endpoint)
                    .header("Authorization", format!("Bearer {api_key}"))
                    .multipart(form)
                    .send()
                    .await
                    .map_err(|e| PipelineError::SttError(format!("API request: {e}")))?;

                #[derive(Deserialize)]
                struct WhisperResp {
                    text: String,
                }

                let body: WhisperResp = resp
                    .json()
                    .await
                    .map_err(|e| PipelineError::SttError(format!("API parse: {e}")))?;

                Ok(body.text)
            }
            SttBackend::WebSpeech => {
                // WebSpeech runs client-side; the Hub receives text directly.
                // This branch should not be called from the server pipeline.
                Err(PipelineError::SttError(
                    "WebSpeech STT runs client-side only".into(),
                ))
            }
        }
    }

    /// Translation stage: convert text between languages.
    async fn run_translate(
        &self,
        text: &str,
        from: Language,
        to: Language,
    ) -> Result<String, PipelineError> {
        if from == to {
            return Ok(text.to_string());
        }

        // Check cache
        let cache_key = TranslationCache::cache_key(text, from, to);
        {
            let mut cache = self.cache.lock().await;
            if let Some(cached) = cache.get(&cache_key) {
                return Ok(cached.to_string());
            }
        }

        let result = match &self.translator {
            TranslateBackend::LlmLocal { endpoint, .. } => {
                let client = reqwest::Client::new();
                let prompt = format!(
                    "Translate the following {} text to {}. Output ONLY the translation, nothing else.\n\n{}",
                    from.display_name(),
                    to.display_name(),
                    text
                );

                #[derive(Serialize)]
                struct LlmReq {
                    prompt: String,
                    max_tokens: u32,
                    temperature: f32,
                }

                #[derive(Deserialize)]
                struct LlmResp {
                    content: String,
                }

                let resp = client
                    .post(format!("{endpoint}/v1/completions"))
                    .json(&LlmReq {
                        prompt,
                        max_tokens: 256,
                        temperature: 0.1,
                    })
                    .send()
                    .await
                    .map_err(|e| {
                        PipelineError::TranslateError(format!("LLM request: {e}"))
                    })?;

                let body: LlmResp = resp.json().await.map_err(|e| {
                    PipelineError::TranslateError(format!("LLM parse: {e}"))
                })?;

                body.content.trim().to_string()
            }

            TranslateBackend::GoogleApi { api_key } => {
                let client = reqwest::Client::new();
                let url = format!(
                    "https://translation.googleapis.com/language/translate/v2?key={api_key}"
                );

                #[derive(Serialize)]
                struct GoogleReq<'a> {
                    q: &'a str,
                    source: &'a str,
                    target: &'a str,
                    format: &'a str,
                }

                #[derive(Deserialize)]
                struct GoogleResp {
                    data: GoogleData,
                }

                #[derive(Deserialize)]
                struct GoogleData {
                    translations: Vec<GoogleTranslation>,
                }

                #[derive(Deserialize)]
                struct GoogleTranslation {
                    #[serde(rename = "translatedText")]
                    translated_text: String,
                }

                let resp = client
                    .post(&url)
                    .json(&GoogleReq {
                        q: text,
                        source: from.iso639(),
                        target: to.iso639(),
                        format: "text",
                    })
                    .send()
                    .await
                    .map_err(|e| {
                        PipelineError::TranslateError(format!("Google API: {e}"))
                    })?;

                let body: GoogleResp = resp.json().await.map_err(|e| {
                    PipelineError::TranslateError(format!("Google parse: {e}"))
                })?;

                body.data
                    .translations
                    .first()
                    .map(|t| t.translated_text.clone())
                    .unwrap_or_else(|| text.to_string())
            }

            TranslateBackend::DeepL { api_key } => {
                let client = reqwest::Client::new();

                #[derive(Serialize)]
                struct DeepLReq<'a> {
                    text: Vec<&'a str>,
                    source_lang: &'a str,
                    target_lang: &'a str,
                }

                #[derive(Deserialize)]
                struct DeepLResp {
                    translations: Vec<DeepLTranslation>,
                }

                #[derive(Deserialize)]
                struct DeepLTranslation {
                    text: String,
                }

                // DeepL uses uppercase codes, JA->JA for target
                let target = to.iso639().to_uppercase();
                let source = from.iso639().to_uppercase();

                let resp = client
                    .post("https://api-free.deepl.com/v2/translate")
                    .header("Authorization", format!("DeepL-Auth-Key {api_key}"))
                    .json(&DeepLReq {
                        text: vec![text],
                        source_lang: &source,
                        target_lang: &target,
                    })
                    .send()
                    .await
                    .map_err(|e| {
                        PipelineError::TranslateError(format!("DeepL API: {e}"))
                    })?;

                let body: DeepLResp = resp.json().await.map_err(|e| {
                    PipelineError::TranslateError(format!("DeepL parse: {e}"))
                })?;

                body.translations
                    .first()
                    .map(|t| t.text.clone())
                    .unwrap_or_else(|| text.to_string())
            }

            TranslateBackend::Dictionary => {
                dictionary_lookup(text, from, to)
            }
        };

        // Store in cache
        {
            let mut cache = self.cache.lock().await;
            cache.insert(cache_key, result.clone());
        }

        Ok(result)
    }

    /// TTS stage: synthesize translated text to audio.
    async fn run_tts(
        &self,
        text: &str,
        lang: Language,
    ) -> Result<Vec<i16>, PipelineError> {
        match &self.tts {
            TtsBackend::PiperLocal {
                model_path,
                binary_path,
            } => {
                let mut child = std::process::Command::new(binary_path)
                    .args(["--model", model_path, "--output_raw"])
                    .stdin(std::process::Stdio::piped())
                    .stdout(std::process::Stdio::piped())
                    .spawn()
                    .map_err(|e| PipelineError::TtsError(format!("piper spawn: {e}")))?;
                {
                    use std::io::Write;
                    if let Some(ref mut stdin) = child.stdin {
                        stdin.write_all(text.as_bytes()).ok();
                    }
                    drop(child.stdin.take());
                }
                let output = child
                    .wait_with_output()
                    .map_err(|e| PipelineError::TtsError(format!("piper: {e}")))?;

                // Piper outputs raw 16-bit PCM at 22050 Hz.
                // Resample to 16000 Hz for consistency.
                let raw = &output.stdout;
                let samples: Vec<i16> = raw
                    .chunks_exact(2)
                    .map(|c| i16::from_le_bytes([c[0], c[1]]))
                    .collect();

                Ok(resample_linear(&samples, 22050, 16000))
            }

            TtsBackend::EspeakLocal => {
                let voice = match lang {
                    Language::Ja => "ja",
                    Language::En => "en",
                    Language::Zh => "zh",
                    Language::Ko => "ko",
                    Language::Es => "es",
                    Language::Fr => "fr",
                };

                let output = tokio::process::Command::new("espeak-ng")
                    .args([
                        "-v", voice,
                        "--stdout",
                        text,
                    ])
                    .output()
                    .await
                    .map_err(|e| PipelineError::TtsError(format!("espeak-ng: {e}")))?;

                if !output.status.success() {
                    return Err(PipelineError::TtsError(
                        "espeak-ng failed".into(),
                    ));
                }

                // espeak-ng --stdout produces WAV — skip 44-byte header
                let raw = if output.stdout.len() > 44 {
                    &output.stdout[44..]
                } else {
                    &output.stdout
                };

                let samples: Vec<i16> = raw
                    .chunks_exact(2)
                    .map(|c| i16::from_le_bytes([c[0], c[1]]))
                    .collect();

                // espeak-ng default is 22050 Hz
                Ok(resample_linear(&samples, 22050, 16000))
            }

            TtsBackend::WebSpeech => {
                // WebSpeech runs client-side; no server audio generated.
                Ok(Vec::new())
            }
        }
    }
}

// ---- Pipeline Error ----

#[derive(Debug, thiserror::Error)]
pub enum PipelineError {
    #[error("STT error: {0}")]
    SttError(String),
    #[error("Translation error: {0}")]
    TranslateError(String),
    #[error("TTS error: {0}")]
    TtsError(String),
    #[error("Empty input — no speech detected")]
    EmptyInput,
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

// ---- Channel-based Pipeline Runner ----

/// Runs the pipeline as a tokio task, receiving requests via mpsc channel
/// and sending responses back. Integrates with Hub's mixer.
pub struct PipelineRunner {
    pipeline: Arc<TranslationPipeline>,
    rx: mpsc::Receiver<(TranslateRequest, mpsc::Sender<TranslateResponse>)>,
}

impl PipelineRunner {
    /// Create a runner and return the sender for submitting requests.
    pub fn new(
        pipeline: TranslationPipeline,
        buffer: usize,
    ) -> (
        Self,
        mpsc::Sender<(TranslateRequest, mpsc::Sender<TranslateResponse>)>,
    ) {
        let (tx, rx) = mpsc::channel(buffer);
        let runner = Self {
            pipeline: Arc::new(pipeline),
            rx,
        };
        (runner, tx)
    }

    /// Run the pipeline loop. Call from a tokio::spawn.
    pub async fn run(mut self) {
        while let Some((req, resp_tx)) = self.rx.recv().await {
            let pipeline = Arc::clone(&self.pipeline);
            tokio::spawn(async move {
                match pipeline.process(req).await {
                    Ok(resp) => {
                        let _ = resp_tx.send(resp).await;
                    }
                    Err(e) => {
                        tracing::warn!("Translation pipeline error: {e}");
                    }
                }
            });
        }
    }
}

// ---- Utility Functions ----

/// Write PCM samples as a 16-bit mono WAV to a temporary file.
fn write_temp_wav(samples: &[i16]) -> Result<String, PipelineError> {
    use std::io::Write;

    let path = format!("/tmp/moji_stt_{}.wav", std::process::id());
    let mut f = std::fs::File::create(&path)?;

    let data_len = (samples.len() * 2) as u32;
    let file_len = data_len + 36;

    // WAV header (44 bytes)
    f.write_all(b"RIFF")?;
    f.write_all(&file_len.to_le_bytes())?;
    f.write_all(b"WAVE")?;
    f.write_all(b"fmt ")?;
    f.write_all(&16u32.to_le_bytes())?; // chunk size
    f.write_all(&1u16.to_le_bytes())?; // PCM
    f.write_all(&1u16.to_le_bytes())?; // mono
    f.write_all(&16000u32.to_le_bytes())?; // sample rate
    f.write_all(&32000u32.to_le_bytes())?; // byte rate
    f.write_all(&2u16.to_le_bytes())?; // block align
    f.write_all(&16u16.to_le_bytes())?; // bits per sample
    f.write_all(b"data")?;
    f.write_all(&data_len.to_le_bytes())?;

    for &s in samples {
        f.write_all(&s.to_le_bytes())?;
    }

    Ok(path)
}

/// Encode PCM samples as WAV bytes (in-memory).
fn encode_wav(samples: &[i16]) -> Vec<u8> {
    let data_len = (samples.len() * 2) as u32;
    let file_len = data_len + 36;
    let mut buf = Vec::with_capacity(44 + data_len as usize);

    buf.extend_from_slice(b"RIFF");
    buf.extend_from_slice(&file_len.to_le_bytes());
    buf.extend_from_slice(b"WAVE");
    buf.extend_from_slice(b"fmt ");
    buf.extend_from_slice(&16u32.to_le_bytes());
    buf.extend_from_slice(&1u16.to_le_bytes());
    buf.extend_from_slice(&1u16.to_le_bytes());
    buf.extend_from_slice(&16000u32.to_le_bytes());
    buf.extend_from_slice(&32000u32.to_le_bytes());
    buf.extend_from_slice(&2u16.to_le_bytes());
    buf.extend_from_slice(&16u16.to_le_bytes());
    buf.extend_from_slice(b"data");
    buf.extend_from_slice(&data_len.to_le_bytes());

    for &s in samples {
        buf.extend_from_slice(&s.to_le_bytes());
    }

    buf
}

/// Simple linear resampling from `from_rate` to `to_rate`.
fn resample_linear(samples: &[i16], from_rate: u32, to_rate: u32) -> Vec<i16> {
    if from_rate == to_rate || samples.is_empty() {
        return samples.to_vec();
    }

    let ratio = from_rate as f64 / to_rate as f64;
    let out_len = (samples.len() as f64 / ratio).ceil() as usize;
    let mut out = Vec::with_capacity(out_len);

    for i in 0..out_len {
        let src_pos = i as f64 * ratio;
        let idx = src_pos as usize;
        let frac = src_pos - idx as f64;

        let s0 = samples[idx] as f64;
        let s1 = if idx + 1 < samples.len() {
            samples[idx + 1] as f64
        } else {
            s0
        };

        let interpolated = s0 + frac * (s1 - s0);
        out.push(interpolated.round() as i16);
    }

    out
}

/// Minimal dictionary-based translation fallback.
fn dictionary_lookup(text: &str, from: Language, to: Language) -> String {
    use Language::*;

    let lower = text.trim().to_lowercase();

    // Only cover the most common phrases as a last-resort fallback.
    let result = match (from, to) {
        (En, Ja) => match lower.as_str() {
            "hello" => "こんにちは",
            "thank you" | "thanks" => "ありがとう",
            "goodbye" | "bye" => "さようなら",
            "yes" => "はい",
            "no" => "いいえ",
            "please" => "お願いします",
            "sorry" | "excuse me" => "すみません",
            "good morning" => "おはようございます",
            "good evening" => "こんばんは",
            "how are you" | "how are you?" => "お元気ですか",
            _ => return format!("[JA] {text}"),
        },
        (Ja, En) => match lower.as_str() {
            "こんにちは" => "Hello",
            "ありがとう" | "ありがとうございます" => "Thank you",
            "さようなら" => "Goodbye",
            "はい" => "Yes",
            "いいえ" => "No",
            "お願いします" => "Please",
            "すみません" => "Excuse me",
            "おはようございます" | "おはよう" => "Good morning",
            "こんばんは" => "Good evening",
            "お元気ですか" => "How are you?",
            _ => return format!("[EN] {text}"),
        },
        _ => return format!("[{}] {text}", to.iso639().to_uppercase()),
    };

    result.to_string()
}

// ---- Tests ----

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_language_codes() {
        assert_eq!(Language::Ja.bcp47(), "ja-JP");
        assert_eq!(Language::En.iso639(), "en");
        assert_eq!(Language::Fr.display_name(), "French");
    }

    #[test]
    fn test_dictionary_lookup() {
        let result = dictionary_lookup("hello", Language::En, Language::Ja);
        assert_eq!(result, "こんにちは");

        let result = dictionary_lookup("ありがとう", Language::Ja, Language::En);
        assert_eq!(result, "Thank you");

        // Unknown phrase returns tagged original
        let result = dictionary_lookup("abcdef", Language::En, Language::Ja);
        assert!(result.starts_with("[JA]"));
    }

    #[test]
    fn test_cache() {
        let mut cache = TranslationCache::new(3);
        cache.insert("a".into(), "1".into());
        cache.insert("b".into(), "2".into());
        cache.insert("c".into(), "3".into());

        assert_eq!(cache.get("a"), Some("1"));

        // Insert 4th, should evict "b" (oldest after "a" was refreshed)
        cache.insert("d".into(), "4".into());
        assert_eq!(cache.get("b"), None);
        assert_eq!(cache.get("c"), Some("3"));
    }

    #[test]
    fn test_resample_identity() {
        let samples = vec![100, 200, 300, 400];
        let out = resample_linear(&samples, 16000, 16000);
        assert_eq!(out, samples);
    }

    #[test]
    fn test_resample_downsample() {
        // 4 samples at 16kHz -> ~2 samples at 8kHz
        let samples = vec![0, 1000, 2000, 3000];
        let out = resample_linear(&samples, 16000, 8000);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0], 0);
    }

    #[test]
    fn test_encode_wav() {
        let samples = vec![0i16; 100];
        let wav = encode_wav(&samples);
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(&wav[8..12], b"WAVE");
        assert_eq!(wav.len(), 44 + 200);
    }

    #[test]
    fn test_same_language_passthrough() {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        let pipeline = TranslationPipeline::new(
            SttBackend::WebSpeech,
            TranslateBackend::Dictionary,
            TtsBackend::WebSpeech,
        );
        rt.block_on(async {
            let result = pipeline
                .run_translate("hello", Language::En, Language::En)
                .await
                .unwrap();
            assert_eq!(result, "hello");
        });
    }

    #[test]
    fn test_all_language_bcp47_codes() {
        let languages = [Language::Ja, Language::En, Language::Zh, Language::Ko, Language::Es, Language::Fr];
        let expected_bcp47 = ["ja-JP", "en-US", "zh-CN", "ko-KR", "es-ES", "fr-FR"];
        let expected_iso639 = ["ja", "en", "zh", "ko", "es", "fr"];

        for (i, lang) in languages.iter().enumerate() {
            assert_eq!(lang.bcp47(), expected_bcp47[i], "bcp47 mismatch for {:?}", lang);
            assert_eq!(lang.iso639(), expected_iso639[i], "iso639 mismatch for {:?}", lang);
            assert!(!lang.display_name().is_empty(), "display_name should not be empty for {:?}", lang);
        }
    }

    #[test]
    fn test_pipeline_error_display() {
        let err_stt = PipelineError::SttError("test".into());
        assert!(format!("{err_stt}").contains("STT error"));

        let err_translate = PipelineError::TranslateError("fail".into());
        assert!(format!("{err_translate}").contains("Translation error"));

        let err_tts = PipelineError::TtsError("no voice".into());
        assert!(format!("{err_tts}").contains("TTS error"));

        let err_empty = PipelineError::EmptyInput;
        assert!(format!("{err_empty}").contains("Empty input"));
    }

    #[test]
    fn test_cache_eviction_at_capacity() {
        let mut cache = TranslationCache::new(2);
        cache.insert("a".into(), "1".into());
        cache.insert("b".into(), "2".into());

        // Cache is full (capacity=2), inserting "c" should evict "a"
        cache.insert("c".into(), "3".into());
        assert_eq!(cache.get("a"), None, "oldest entry should be evicted");
        assert_eq!(cache.get("b"), Some("2"), "non-evicted entry should remain");
        assert_eq!(cache.get("c"), Some("3"), "newest entry should be present");

        // Now "b" was accessed (refreshed), insert "d" should evict "c" (oldest in order)
        // After get("b"), order = [c, b]; after get("c"), order = [b, c]
        // Actually after the gets above: order after insert("c") = [b, c]
        // get("b") -> order = [c, b]; get("c") -> order = [b, c]
        cache.insert("d".into(), "4".into());
        // "b" should be evicted (it was first in order after "c" was moved to end)
        assert_eq!(cache.get("b"), None, "b should be evicted after c was refreshed");
        assert_eq!(cache.get("c"), Some("3"));
        assert_eq!(cache.get("d"), Some("4"));
    }
}
