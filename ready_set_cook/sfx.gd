class_name Sfx
extends Node
# Tiny procedural sound engine: no audio files needed.

const RATE := 22050
var enabled := true
var streams := {}
var players: Array[AudioStreamPlayer] = []
var next_player := 0
var music_player: AudioStreamPlayer
var sizzle_player: AudioStreamPlayer
var sizzle_level := 0.0
const MRATE := 11025


func _ready() -> void:
	# layered synth: each layer = {f0, f1, t0, dur, wave, vol, decay, lp}; wave 0 sine 1 square 2 noise 3 triangle
	streams["click"] = _synth([_l(900, 600, 0.0, 0.05, 0, 0.45, 40)])
	streams["pop"] = _synth([_l(380, 900, 0.0, 0.09, 0, 0.5, 18), _l(0, 0, 0.0, 0.03, 2, 0.12, 60, 0.4)])
	streams["chop"] = _synth([_l(0, 0, 0.0, 0.05, 2, 0.7, 70, 0.55), _l(260, 90, 0.0, 0.07, 0, 0.6, 40),
		_l(0, 0, 0.09, 0.05, 2, 0.55, 70, 0.6), _l(240, 80, 0.09, 0.07, 0, 0.5, 40),
		_l(0, 0, 0.18, 0.05, 2, 0.45, 70, 0.6), _l(230, 80, 0.18, 0.07, 0, 0.4, 40)])
	streams["ding"] = _synth(_bell(1318.0, 0.5, 0.42))
	streams["bell"] = _synth(_bell(1760.0, 0.4, 0.3))
	streams["coin"] = _synth(_bell(1568.0, 0.18, 0.28) + _shift(_bell(2093.0, 0.35, 0.28), 0.07))
	streams["error"] = _synth([_l(210, 150, 0.0, 0.16, 1, 0.3, 6, 0.0), _l(190, 120, 0.12, 0.2, 1, 0.3, 6, 0.0)])
	streams["burn"] = _synth([_l(0, 0, 0.0, 0.6, 2, 0.55, 5, 0.25), _l(120, 50, 0.0, 0.35, 0, 0.4, 7)])
	streams["tick"] = _synth([_l(740, 740, 0.0, 0.12, 0, 0.5, 22)])
	streams["go"] = _synth(_bell(988.0, 0.5, 0.4) + _shift(_bell(1318.0, 0.5, 0.4), 0.1) + _shift(_bell(1760.0, 0.7, 0.45), 0.2))
	streams["win"] = _synth(_bell(523.0, 0.35, 0.35) + _shift(_bell(659.0, 0.35, 0.35), 0.13) + _shift(_bell(784.0, 0.35, 0.35), 0.26) + _shift(_bell(1047.0, 0.9, 0.42), 0.4))
	streams["lose"] = _synth([_l(330, 250, 0.0, 0.3, 3, 0.45, 5), _l(250, 160, 0.28, 0.5, 3, 0.45, 4)])
	streams["star"] = _synth(_bell(1175.0, 0.4, 0.4) + _shift(_bell(1568.0, 0.5, 0.4), 0.06))
	streams["step"] = _synth([_l(150, 70, 0.0, 0.06, 0, 0.3, 45), _l(0, 0, 0.0, 0.035, 2, 0.12, 80, 0.3)])
	streams["sizzle"] = _make_sizzle()
	for i in 8:
		var p := AudioStreamPlayer.new()
		add_child(p)
		players.append(p)
	music_player = AudioStreamPlayer.new()
	music_player.volume_db = -13.0
	add_child(music_player)
	sizzle_player = AudioStreamPlayer.new()
	sizzle_player.stream = streams["sizzle"]
	sizzle_player.volume_db = -60.0
	add_child(sizzle_player)


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
	# a touch of random pitch so repeated sounds don't machine-gun
	p.pitch_scale = pitch * randf_range(0.96, 1.04)
	p.volume_db = -9.0 if sound == "step" else 0.0
	p.play()


# 0..1 : how much is cooking right now (drives a looping sizzle)
func set_sizzle(target: float, delta: float) -> void:
	if sizzle_player == null:
		return
	sizzle_level = move_toward(sizzle_level, target if enabled else 0.0, delta * 2.0)
	if sizzle_level <= 0.01:
		if sizzle_player.playing:
			sizzle_player.stop()
		return
	if not sizzle_player.playing:
		sizzle_player.play()
	sizzle_player.volume_db = lerpf(-34.0, -15.0, sizzle_level)


func _l(f0: float, f1: float, t0: float, dur: float, wave: int, vol: float, decay: float, lp: float = 0.0) -> Dictionary:
	return {"f0": f0, "f1": f1, "t0": t0, "dur": dur, "wave": wave, "vol": vol, "decay": decay, "lp": lp}


# a bell: a few inharmonic sine partials with exponential decay
func _bell(f: float, dur: float, vol: float) -> Array:
	var out: Array = []
	var partials := [[1.0, 1.0, 7.0], [2.76, 0.5, 11.0], [5.4, 0.25, 18.0], [8.9, 0.12, 26.0]]
	for p in partials:
		out.append(_l(f * float(p[0]), f * float(p[0]), 0.0, dur, 0, vol * float(p[1]), float(p[2]) * (0.45 / dur)))
	return out


func _shift(layers: Array, dt: float) -> Array:
	var out: Array = []
	for l in layers:
		var c: Dictionary = (l as Dictionary).duplicate()
		c["t0"] = float(c["t0"]) + dt
		out.append(c)
	return out


func _synth(layers: Array) -> AudioStreamWAV:
	var total := 0.05
	for l in layers:
		total = maxf(total, float(l["t0"]) + float(l["dur"]))
	var n := int(total * RATE)
	var buf := PackedFloat32Array()
	buf.resize(n)
	for l in layers:
		var start := int(float(l["t0"]) * RATE)
		var len := int(float(l["dur"]) * RATE)
		var phase := 0.0
		var y := 0.0
		for i in len:
			var idx := start + i
			if idx >= n:
				break
			var u := float(i) / float(len)
			phase += lerpf(float(l["f0"]), float(l["f1"]), u) / RATE
			var smp := 0.0
			match int(l["wave"]):
				0: smp = sin(phase * TAU)
				1: smp = 1.0 if fmod(phase, 1.0) < 0.5 else -1.0
				2: smp = randf() * 2.0 - 1.0
				_: smp = absf(fmod(phase, 1.0) * 4.0 - 2.0) - 1.0
			var lp := float(l["lp"])
			if lp > 0.0:
				y += lp * (smp - y)
				smp = y * 2.2
			var t := float(i) / RATE
			var env := minf(1.0, t * 400.0) * exp(-t * float(l["decay"])) * (1.0 - u * u * 0.3)
			buf[idx] += smp * float(l["vol"]) * env
	var data := PackedByteArray()
	data.resize(n * 2)
	for i in n:
		data.encode_s16(i * 2, int(clampf(buf[i], -1.0, 1.0) * 30000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	return w


# a looping pan sizzle: filtered noise with random crackle pops
func _make_sizzle() -> AudioStreamWAV:
	var n := RATE
	var data := PackedByteArray()
	data.resize(n * 2)
	var y := 0.0
	var crack := 0.0
	for i in n:
		var x := randf() * 2.0 - 1.0
		y += 0.5 * (x - y)
		if randf() < 0.0012:
			crack = 1.0
		crack *= 0.995
		var s := y * 0.28 + crack * (randf() * 2.0 - 1.0) * 0.5
		data.encode_s16(i * 2, int(clampf(s, -1.0, 1.0) * 24000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = RATE
	w.stereo = false
	w.data = data
	w.loop_mode = AudioStreamWAV.LOOP_FORWARD
	w.loop_begin = 0
	w.loop_end = n
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
