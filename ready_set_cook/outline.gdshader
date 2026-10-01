shader_type spatial;
// Ink outline: an inflated copy of the mesh drawn only where its back faces show (inverted hull).
render_mode cull_front, unshaded, depth_draw_opaque;
uniform float width = 0.022;
uniform vec4 ink : source_color = vec4(0.08, 0.045, 0.03, 1.0);

void vertex() {
	VERTEX += NORMAL * width;
}

void fragment() {
	ALBEDO = ink.rgb;
}
