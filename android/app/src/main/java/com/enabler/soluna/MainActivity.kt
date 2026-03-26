package com.enabler.soluna

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.widget.ProgressBar
import android.widget.SeekBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton

class MainActivity : AppCompatActivity() {

    companion object {
        private const val PERMISSION_REQUEST_CODE = 1001
    }

    private lateinit var statusText: TextView
    private lateinit var peerCount: TextView
    private lateinit var audioLevelMeter: ProgressBar
    private lateinit var btnMic: MaterialButton
    private lateinit var volumeSlider: SeekBar

    private lateinit var channelButtons: Map<String, MaterialButton>
    private var currentChannel = "soluna"
    private var micEnabled = false

    private lateinit var audioEngine: AudioEngine
    private lateinit var udpTransport: UdpTransport

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        bindViews()
        setupAudioEngine()
        setupTransport()
        setupListeners()

        if (hasPermissions()) {
            startNetwork()
        } else {
            requestPermissions()
        }
    }

    private fun bindViews() {
        statusText = findViewById(R.id.statusText)
        peerCount = findViewById(R.id.peerCount)
        audioLevelMeter = findViewById(R.id.audioLevelMeter)
        btnMic = findViewById(R.id.btnMic)
        volumeSlider = findViewById(R.id.volumeSlider)

        channelButtons = mapOf(
            "soluna" to findViewById(R.id.btnSoluna),
            "voice" to findViewById(R.id.btnVoice),
            "music" to findViewById(R.id.btnMusic),
            "ambient" to findViewById(R.id.btnAmbient)
        )
    }

    private fun setupAudioEngine() {
        audioEngine = AudioEngine(
            onAudioCaptured = { adpcmData ->
                udpTransport.sendAudioPacket(adpcmData)
            },
            onAudioLevel = { level ->
                runOnUiThread {
                    audioLevelMeter.progress = level
                }
            }
        )
    }

    private fun setupTransport() {
        val deviceId = getDeviceId()

        udpTransport = UdpTransport(
            deviceId = deviceId,
            onPacketReceived = { packet ->
                if (SolunaProtocol.isAdpcm(packet.flags)) {
                    audioEngine.playAdpcmPacket(packet.payload)
                }
            },
            onPeerCountChanged = { count ->
                runOnUiThread {
                    peerCount.text = count.toString()
                    statusText.text = if (count > 0) {
                        "Connected - peers: $count"
                    } else {
                        getString(R.string.status_connected)
                    }
                }
            }
        )
    }

    private fun setupListeners() {
        // Channel buttons
        for ((name, button) in channelButtons) {
            button.setOnClickListener {
                selectChannel(name)
            }
        }

        // Mic toggle
        btnMic.setOnClickListener {
            toggleMic()
        }

        // Volume slider
        volumeSlider.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar, progress: Int, fromUser: Boolean) {
                audioEngine.setPlaybackVolume(progress / 100f)
            }
            override fun onStartTrackingTouch(seekBar: SeekBar) {}
            override fun onStopTrackingTouch(seekBar: SeekBar) {}
        })
    }

    private fun selectChannel(name: String) {
        currentChannel = name
        udpTransport.setChannel(name)

        // Update button styles
        for ((channelName, button) in channelButtons) {
            if (channelName == name) {
                button.setBackgroundColor(0xFF00D4AA.toInt())
                button.setTextColor(0xFF000000.toInt())
            } else {
                button.setBackgroundColor(0x00000000)
                button.setTextColor(0xFF00D4AA.toInt())
                button.strokeColor = android.content.res.ColorStateList.valueOf(0xFF00D4AA.toInt())
            }
        }
    }

    private fun toggleMic() {
        micEnabled = !micEnabled

        if (micEnabled) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED
            ) {
                audioEngine.startCapture()
                btnMic.text = getString(R.string.mic_on)
                btnMic.setBackgroundColor(0xFF00D4AA.toInt())
                btnMic.setTextColor(0xFF000000.toInt())
            } else {
                micEnabled = false
                requestPermissions()
            }
        } else {
            audioEngine.stopCapture()
            btnMic.text = getString(R.string.mic_off)
            btnMic.setBackgroundColor(0xFF333333.toInt())
            btnMic.setTextColor(0xFF888888.toInt())
            audioLevelMeter.progress = 0
        }
    }

    private fun startNetwork() {
        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
        udpTransport.start(wifiManager)
        audioEngine.startPlayback()
        statusText.text = getString(R.string.status_connected)
    }

    private fun hasPermissions(): Boolean {
        return ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    private fun requestPermissions() {
        ActivityCompat.requestPermissions(
            this,
            arrayOf(Manifest.permission.RECORD_AUDIO),
            PERMISSION_REQUEST_CODE
        )
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_REQUEST_CODE) {
            startNetwork()
        }
    }

    private fun getDeviceId(): String {
        // Generate a stable device ID using shared preferences
        val prefs = getSharedPreferences("soluna", Context.MODE_PRIVATE)
        var id = prefs.getString("device_id", null)
        if (id == null) {
            id = "android-${Build.MODEL}-${System.currentTimeMillis().toString(36)}"
            prefs.edit().putString("device_id", id).apply()
        }
        return id
    }

    override fun onDestroy() {
        super.onDestroy()
        audioEngine.release()
        udpTransport.stop()
    }
}
