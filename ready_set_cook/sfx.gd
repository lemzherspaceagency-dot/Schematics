class_name Sfx
extends Node
# Tiny procedural sound engine: no audio files needed.

const RATE := 22050
var enabled := true
var streams := {}
var players: Array[AudioStreamPlayer] = []
var next_player := 0


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
