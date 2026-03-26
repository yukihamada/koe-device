package com.enabler.soluna

import android.net.wifi.WifiManager
import java.net.DatagramPacket
import java.net.InetAddress
import java.net.MulticastSocket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * UDP multicast transport for the Soluna protocol.
 * Sends/receives audio packets on 239.42.42.1:4242.
 */
class UdpTransport(
    private val deviceId: String,
    private val onPacketReceived: (SolunaProtocol.ParsedPacket) -> Unit,
    private val onPeerCountChanged: (Int) -> Unit
) {
    private val deviceHash = SolunaProtocol.fnv1a(deviceId)
    private val sequence = AtomicInteger(0)
    private val running = AtomicBoolean(false)

    private var socket: MulticastSocket? = null
    private var multicastGroup: InetAddress? = null
    private var receiveThread: Thread? = null
    private var heartbeatThread: Thread? = null
    private var multicastLock: WifiManager.MulticastLock? = null

    @Volatile
    var currentChannelHash: Int = SolunaProtocol.fnv1a("soluna")
        private set

    // Track peers: deviceHash -> last seen timestamp
    private val peers = ConcurrentHashMap<Int, Long>()
    private val PEER_TIMEOUT_MS = 15_000L

    fun start(wifiManager: WifiManager?) {
        if (running.getAndSet(true)) return

        // Acquire multicast lock so the device receives multicast packets
        multicastLock = wifiManager?.createMulticastLock("soluna_multicast")?.apply {
            setReferenceCounted(false)
            acquire()
        }

        multicastGroup = InetAddress.getByName(SolunaProtocol.MULTICAST_GROUP)
        socket = MulticastSocket(SolunaProtocol.MULTICAST_PORT).apply {
            reuseAddress = true
            joinGroup(multicastGroup)
            soTimeout = 1000 // 1s timeout for clean shutdown
        }

        startReceiveLoop()
        startHeartbeatLoop()
    }

    fun stop() {
        if (!running.getAndSet(false)) return

        heartbeatThread?.interrupt()
        receiveThread?.interrupt()

        try {
            socket?.leaveGroup(multicastGroup)
            socket?.close()
        } catch (_: Exception) {}

        multicastLock?.release()
        peers.clear()
    }

    fun setChannel(channelName: String) {
        currentChannelHash = SolunaProtocol.fnv1a(channelName)
        peers.clear()
        onPeerCountChanged(0)
    }

    fun sendAudioPacket(adpcmData: ByteArray) {
        if (!running.get()) return

        val packet = SolunaProtocol.buildPacket(
            deviceHash = deviceHash,
            sequence = sequence.getAndIncrement(),
            channelHash = currentChannelHash,
            timestampMs = System.currentTimeMillis(),
            flags = SolunaProtocol.FLAG_ADPCM,
            payload = adpcmData
        )

        sendRaw(packet)
    }

    private fun sendHeartbeat() {
        val packet = SolunaProtocol.buildPacket(
            deviceHash = deviceHash,
            sequence = sequence.getAndIncrement(),
            channelHash = currentChannelHash,
            timestampMs = System.currentTimeMillis(),
            flags = SolunaProtocol.FLAG_HEARTBEAT
        )

        sendRaw(packet)
    }

    private fun sendRaw(data: ByteArray) {
        try {
            val dgram = DatagramPacket(
                data, data.size,
                multicastGroup, SolunaProtocol.MULTICAST_PORT
            )
            socket?.send(dgram)
        } catch (_: Exception) {}
    }

    private fun startReceiveLoop() {
        receiveThread = Thread({
            val buf = ByteArray(2048)
            while (running.get()) {
                try {
                    val dgram = DatagramPacket(buf, buf.size)
                    socket?.receive(dgram)

                    val parsed = SolunaProtocol.parsePacket(buf, dgram.length) ?: continue

                    // Skip own packets
                    if (parsed.deviceHash == deviceHash) continue

                    // Only process packets on our channel
                    if (parsed.channelHash != currentChannelHash) continue

                    // Track peer
                    val now = System.currentTimeMillis()
                    peers[parsed.deviceHash] = now
                    pruneOldPeers(now)

                    if (!SolunaProtocol.isHeartbeat(parsed.flags)) {
                        onPacketReceived(parsed)
                    }
                } catch (_: java.net.SocketTimeoutException) {
                    pruneOldPeers(System.currentTimeMillis())
                } catch (_: Exception) {
                    if (!running.get()) break
                }
            }
        }, "soluna-receive").apply {
            isDaemon = true
            start()
        }
    }

    private fun startHeartbeatLoop() {
        heartbeatThread = Thread({
            while (running.get()) {
                try {
                    sendHeartbeat()
                    Thread.sleep(SolunaProtocol.HEARTBEAT_INTERVAL_MS)
                } catch (_: InterruptedException) {
                    break
                }
            }
        }, "soluna-heartbeat").apply {
            isDaemon = true
            start()
        }
    }

    private fun pruneOldPeers(now: Long) {
        val before = peers.size
        peers.entries.removeIf { now - it.value > PEER_TIMEOUT_MS }
        val after = peers.size
        if (before != after) {
            onPeerCountChanged(after)
        }
    }
}
