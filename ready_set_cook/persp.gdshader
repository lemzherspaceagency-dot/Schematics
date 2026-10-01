shader_type canvas_item;
// Tilts the kitchen away from the camera (a cheap perspective view).
// Must match _project()/_unproject() in game_sim.gd.
// Items drawn with draw_set_transform have their vertices in local space, so go through MODEL_MATRIX.
uniform float strength = 0.2;
uniform vec2 size = vec2(1280.0, 720.0);

void vertex() {
	vec2 w = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
	float t = w.y / size.y;
	float k = 1.0 + strength * (1.0 - t);
	float s = 1.0 / k;
	float yy = (log(1.0 + strength) - log(k)) / log(1.0 + strength);
	vec2 p = vec2(size.x * 0.5 + (w.x - size.x * 0.5) * s, yy * size.y);
	VERTEX = (inverse(MODEL_MATRIX) * vec4(p, 0.0, 1.0)).xy;
}
