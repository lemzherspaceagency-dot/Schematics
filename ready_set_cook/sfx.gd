class_name Sfx
extends Node
# Tiny procedural sound engine: no audio files needed.

const RATE := 22050
var enabled := true
var streams := {}
var players: Array[AudioStreamPlayer] = []
var next_player := 0
var music_player: AudioStreamPlayer
const MRATE := 11025


func _ready() -> void:
	# segment = [freq_start, freq_end, seconds, wave(0 sine,1 square,2 noise,3 tri), volume]
	streams["click"] = _make([[700, 700, 0.04, 0, 0.4]])
	streams["pop"] = _make([[450, 900, 0.09, 0, 0.5]])
	streams["chop"] = _make([[0, 0, 0.04, 2, 0.6], [0, 0, 0.03, 2, 0.35]])
	streams["ding"] = _make([[880, 880, 0.1, 0, 0.45], [1320, 1320, 0.22, 0, 0.45]])
	streams["coin"] = _make([[1000, 1000, 0.06, 1, 0.25], [1500, 1500, 0.2, 1, 0.25]])
	streams["error"] = _make([[230, 150, 0.22, 1, 0.3]])
	streams["burn"] = _make([[0, 0, 0.45, 2, 0.45]])
	streams["tick"] = _make([[660, 660, 0.12, 0, 0.5]])
	streams["go"] = _make([[880, 1320, 0.35, 0, 0.55]])
	streams["bell"] = _make([[1568, 1568, 0.3, 0, 0.35]])
	streams["win"] = _make([[523, 523, 0.12, 3, 0.5], [659, 659, 0.12, 3, 0.5], [784, 784, 0.12, 3, 0.5], [1047, 1047, 0.4, 3, 0.55]])
	streams["lose"] = _make([[400, 300, 0.25, 3, 0.5], [300, 200, 0.45, 3, 0.5]])
	streams["star"] = _make([[800, 1600, 0.25, 0, 0.5]])
	for i in 8:
		var p := AudioStreamPlayer.new()
		add_child(p)
		players.append(p)
	music_player = AudioStreamPlayer.new()
	music_player.volume_db = -13.0
	add_child(music_player)


func set_enabled(v: bool) -> void:
	enabled = v
	if music_player == null:
		return
	if v and music_ready and not music_player.playing:
		music_player.play()
	elif not v:
		music_player.stop()


func duck(amount_db: float) -> void:
	if music_player != null:
		music_player.volume_db = amount_db


func play(sound: String, pitch: float = 1.0) -> void:
	if not enabled or not streams.has(sound) or players.is_empty():
		return
	var p := players[next_player]
	next_player = (next_player + 1) % players.size()
	p.stream = streams[sound]
	p.pitch_scale = pitch
	p.play()


func _make(segs: Array) -> AudioStreamWAV:
	var data := PackedByteArray()
	var phase := 0.0
	for seg in segs:
		var f0: float = seg[0]
		var f1: float = seg[1]
		var dur: float = seg[2]
		var wave: int = int(seg[3])
		var vol: float = seg[4]
		var n: int = int(dur * RATE)
		var start: int = data.size()
		data.resize(start + n * 2)
		for i in n:
			var u: float = float(i) / float(n)
			phase += lerpf(f0, f1, u) / RATE
			var s := 0.0
			match wave:
				0: s = sin(phase * TAU)
				1: s = 1.0 if fmod(phase, 1.0) < 0.5 else -1.0
				2: s = randf() * 2.0 - 1.0
				_: s = absf(fmod(phase, 1.0) * 4.0 - 2.0) - 1.0
			var env: float = minf(1.0, u * 20.0) * pow(1.0 - u, 1.5)
			data.encode_s16(start + i * 2, int(clampf(s * vol * env, -1.0, 1.0) * 32767.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	return w


# A cheerful 4-bar loop (C - Am - F - G): bouncy bass, plucky arpeggio, soft kick and hat.
# Built a step at a time so the loading screen can show real progress.
const MUSIC_STEPS := 32
const BPM := 118.0
const CHORDS := [[0, 4, 7], [-3, 0, 4], [-7, -3, 0], [-5, -1, 2]]
const ROOTS := [-24, -27, -31, -29]
const ARP := [0, 1, 2, 1, 2, 1, 2, 1]
var music_buf := PackedFloat32Array()
var music_ready := false


func music_begin() -> void:
	var eighth := 60.0 / BPM / 2.0
	music_buf = PackedFloat32Array()
	music_buf.resize(int(float(MUSIC_STEPS) * eighth * MRATE))


func music_step(i: int) -> void:
	var eighth := 60.0 / BPM / 2.0
	var bar: int = i / 8
	var step: int = i % 8
	var t0: float = i * eighth
	var chord: Array = CHORDS[bar]
	_note(music_buf, t0, _midi(60 + int(chord[ARP[step]]) + 12), 0.34, 0.16, 9.0, 0)
	if step % 2 == 0:
		_note(music_buf, t0, _midi(60 + int(ROOTS[bar]) + (12 if step == 4 else 0)), 0.36, 0.34, 5.0, 1)
	if step == 0 or step == 4:
		_note(music_buf, t0, 90.0, 0.16, 0.5, 18.0, 2)
	if step % 2 == 1:
		_note(music_buf, t0, 0.0, 0.05, 0.06, 60.0, 3)


func music_finish() -> void:
	var total := music_buf.size()
	var data := PackedByteArray()
	data.resize(total * 2)
	for i in total:
		data.encode_s16(i * 2, int(clampf(music_buf[i], -1.0, 1.0) * 30000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = MRATE
	w.stereo = false
	w.data = data
	w.loop_mode = AudioStreamWAV.LOOP_FORWARD
	w.loop_begin = 0
	w.loop_end = total
	music_player.stream = w
	music_buf = PackedFloat32Array()
	music_ready = true
	if enabled:
		music_player.play()


func _midi(m: int) -> float:
	return 440.0 * pow(2.0, (float(m) - 69.0) / 12.0)


# wave: 0 triangle pluck, 1 sine bass, 2 kick (pitch drop), 3 noise hat
func _note(buf: PackedFloat32Array, start_s: float, freq: float, dur: float, vol: float, decay: float, wave: int) -> void:
	var a := int(start_s * MRATE)
	var n := int(dur * MRATE)
	var phase := 0.0
	for j in n:
		var idx := a + j
		if idx >= buf.size():
			idx -= buf.size()
		var t := float(j) / MRATE
		var env := exp(-t * decay) * minf(1.0, t * 300.0)
		var smp := 0.0
		match wave:
			0:
				phase += freq / MRATE
				smp = absf(fmod(phase, 1.0) * 4.0 - 2.0) - 1.0
			1:
				phase += freq / MRATE
				smp = sin(phase * TAU)
			2:
				phase += (freq * (1.0 + 2.5 * exp(-t * 30.0))) / MRATE
				smp = sin(phase * TAU)
			_:
				smp = randf() * 2.0 - 1.0
		buf[idx] += smp * env * vol
