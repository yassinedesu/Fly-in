"""Interactive hardware-accelerated visualizer for Fly-in drone routing."""
from __future__ import annotations

import colorsys
import math

import arcade
import arcade.types

from graph import Graph, Hub, ZoneType

ZONE_COLORS: dict[ZoneType, arcade.types.Color] = {
    ZoneType.NORMAL: arcade.color.LIGHT_GRAY,
    ZoneType.BLOCKED: arcade.color.DIM_GRAY,
    ZoneType.RESTRICTED: arcade.color.RED,
    ZoneType.PRIORITY: arcade.color.GREEN,
}

DRONE_COLORS: list[arcade.types.Color] = [
    arcade.color.YELLOW,
    arcade.color.CYAN,
    arcade.color.ORANGE,
    arcade.color.MAGENTA,
    arcade.color.SPRING_GREEN,
    arcade.color.PINK,
    arcade.color.SKY_BLUE,
    arcade.color.WHITE,
]

COLOR_ALIASES: dict[str, arcade.types.Color] = {
    "DARKRED": arcade.color.DARK_RED,
    "LIME": arcade.color.LIME_GREEN,
    "GREY": arcade.color.GRAY,
}


def resolve_hub_color(
    hub: Hub, anim_time: float = 0.0
) -> arcade.types.Color:
    """Determines hub color prioritizing metadata tags over defaults."""
    if hub.color:
        name = hub.color.strip().upper().replace("-", "_").replace(" ", "_")
        if name == "RAINBOW":
            r, g, b = colorsys.hsv_to_rgb(
                (anim_time * 0.25) % 1.0, 0.85, 0.95
            )
            return arcade.types.Color(
                int(r * 255), int(g * 255), int(b * 255), 255
            )
        val = getattr(arcade.color, name, None) or COLOR_ALIASES.get(name)
        if isinstance(val, arcade.types.Color):
            return val
    if hub.is_start:
        return arcade.color.GREEN
    if hub.is_end:
        return arcade.color.GOLD
    return ZONE_COLORS.get(hub.zone, arcade.color.LIGHT_GRAY)


def point_line_distance(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Calculates point-to-segment distance via vector projection."""
    px, py = p
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    if l2 == 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


class FlyInVisualizer(arcade.Window):
    """Dual-camera continuous visualizer with interpolation and tooltips."""

    def __init__(
        self,
        graph: Graph,
        simulation_data: list[dict[str, str]] | None = None,
        map_name: str = "",
    ) -> None:
        title = (
            f"Fly-in Drone Routing - {map_name}"
            if map_name
            else "Fly-in Drone Routing"
        )
        super().__init__(1024, 768, title, fullscreen=False)
        self.graph = graph
        self.simulation_data = simulation_data or []
        self.background_color = arcade.color.EERIE_BLACK
        self.max_turns = max(0, len(self.simulation_data) - 1)
        self.current_turn = 0.0
        self.playing = True
        self.anim_speed = 2.0
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.default_zoom = 1.0
        self.default_pos: tuple[float, float] = (0.0, 0.0)

        self.positions: dict[str, tuple[float, float]] = {
            h.name: (float(h.x * 140.0), float(h.y * 140.0))
            for h in graph.hubs.values()
        }
        self.drone_colors: dict[str, arcade.types.Color] = {
            f"D{i + 1}": DRONE_COLORS[i % len(DRONE_COLORS)]
            for i in range(graph.drone_count)
        }

        end = graph.end_hub.name if graph.end_hub else ""
        self.drone_paths: dict[str, list[tuple[float, float]]] = {
            d: [] for d in self.drone_colors
        }
        self.occupancy_history: list[dict[str, int]] = []

        for t in range(self.max_turns + 1):
            st = (
                self.simulation_data[t]
                if t < len(self.simulation_data)
                else {}
            )
            occ: dict[str, int] = {}
            for d in self.drone_colors:
                loc = st.get(d, end)
                occ[loc] = occ.get(loc, 0) + 1
                if "-" in loc:
                    u, v = loc.split("-", 1)
                    p1 = self.positions.get(u, (0.0, 0.0))
                    p2 = self.positions.get(v, (0.0, 0.0))
                    mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
                    self.drone_paths[d].append(mid)
                else:
                    self.drone_paths[d].append(
                        self.positions.get(loc, (0.0, 0.0))
                    )
            self.occupancy_history.append(occ)

        self.world_camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()
        self._fit_camera_view()

    def _fit_camera_view(self) -> None:
        """Centers and scales the camera to fit all network hubs."""
        if not self.positions:
            return
        xs = [p[0] for p in self.positions.values()]
        ys = [p[1] for p in self.positions.values()]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        span_x = max(max(xs) - min(xs) + 220.0, 400.0)
        span_y = max(max(ys) - min(ys) + 220.0, 300.0)
        fit = min(1024.0 / span_x, 768.0 / span_y)
        self.default_zoom = max(0.05, min(1.2, fit))
        self.default_pos = (cx, cy)
        self.world_camera.zoom = self.default_zoom
        self.world_camera.position = self.default_pos

    def on_update(self, delta_time: float) -> None:
        """Advances playback timeline."""
        if self.playing and self.max_turns > 0:
            self.current_turn = min(
                float(self.max_turns),
                self.current_turn + delta_time * self.anim_speed,
            )
            if self.current_turn >= self.max_turns:
                self.playing = False

    def on_draw(self) -> None:
        """Renders world entities, lerped drones, and HUD."""
        self.clear()
        self.world_camera.use()
        wm = self.world_camera.unproject((self.mouse_x, self.mouse_y))
        drawn: set[frozenset[str]] = set()
        hov_edge: frozenset[str] | None = None

        for u, conns in self.graph.adj.items():
            p1 = self.positions[u]
            for c in conns:
                pair = frozenset({u, c.v})
                if pair in drawn:
                    continue
                drawn.add(pair)
                p2 = self.positions[c.v]
                dist = point_line_distance((wm.x, wm.y), p1, p2)
                thresh = 12.0 / self.world_camera.zoom
                if dist <= thresh and hov_edge is None:
                    hov_edge = pair
                    arcade.draw_line(
                        p1[0], p1[1], p2[0], p2[1], arcade.color.YELLOW, 4
                    )
                else:
                    arcade.draw_line(
                        p1[0], p1[1], p2[0], p2[1], arcade.color.DARK_GRAY, 3
                    )

        for hub in self.graph.hubs.values():
            hx, hy = self.positions[hub.name]
            hub_col = resolve_hub_color(hub, self.current_turn)
            arcade.draw_circle_filled(hx, hy, 24.0, hub_col)
            arcade.draw_circle_outline(hx, hy, 24.0, arcade.color.BLACK, 2)
            arcade.Text(
                hub.name,
                hx,
                hy + 29,
                arcade.color.WHITE,
                11,
                bold=True,
                anchor_x="center",
            ).draw()

        t0 = int(self.current_turn)
        t1 = min(t0 + 1, self.max_turns)
        prog = self.current_turn % 1.0 if t0 < self.max_turns else 0.0
        for d_id, path in self.drone_paths.items():
            if t0 < len(path):
                p0 = path[t0]
                p1 = path[t1] if t1 < len(path) else p0
                dx = p0[0] + (p1[0] - p0[0]) * prog
                dy = p0[1] + (p1[1] - p0[1]) * prog
                d_col = self.drone_colors.get(d_id, arcade.color.YELLOW)
                arcade.draw_circle_filled(dx, dy, 8.0, d_col)
                arcade.draw_circle_outline(
                    dx, dy, 8.0, arcade.color.BLACK, 1.5
                )
                arcade.Text(
                    d_id,
                    dx,
                    dy - 4,
                    arcade.color.BLACK,
                    8,
                    bold=True,
                    anchor_x="center",
                ).draw()

        self.gui_camera.use()
        end = self.graph.end_hub.name if self.graph.end_hub else ""
        deliv = (
            self.occupancy_history[t0].get(end, 0)
            if t0 < len(self.occupancy_history)
            else 0
        )
        hud = (
            f"Turn: {t0} / {self.max_turns}   "
            f"Delivered: {deliv} / {self.graph.drone_count}"
        )
        arcade.Text(hud, 20, 733, arcade.color.WHITE, 14, bold=True).draw()
        help_txt = (
            "SPACE: Play/Pause | LEFT/RIGHT: Step | R: Restart | "
            "F: Reset View | Drag: Pan | Scroll: Zoom"
        )
        arcade.Text(help_txt, 20, 18, arcade.color.GRAY, 11).draw()
        self._draw_tooltip(wm.x, wm.y, t0)

    def _draw_tooltip(self, wx: float, wy: float, t0: int) -> None:
        """Displays formatted metadata tooltips when hovering nodes/edges."""
        lines: list[str] = []
        for h in self.graph.hubs.values():
            hx, hy = self.positions[h.name]
            if math.hypot(wx - hx, wy - hy) <= 24.0:
                occ = (
                    self.occupancy_history[t0].get(h.name, 0)
                    if t0 < len(self.occupancy_history)
                    else 0
                )
                cap = (
                    self.graph.drone_count
                    if (h.is_start or h.is_end)
                    else h.max_drones
                )
                c_tag = f" | Color: {h.color}" if h.color else ""
                lines = [
                    f"Zone: {h.name}",
                    f"Type: {h.zone.value}{c_tag}",
                    f"Occupied: {occ} / {cap}",
                ]
                break

        if not lines:
            thresh = 12.0 / self.world_camera.zoom
            for u, conns in self.graph.adj.items():
                p1 = self.positions[u]
                for c in conns:
                    p2 = self.positions[c.v]
                    if point_line_distance((wx, wy), p1, p2) <= thresh:
                        occ = 0
                        if t0 < len(self.occupancy_history):
                            hist = self.occupancy_history[t0]
                            occ = (
                                hist.get(f"{u}-{c.v}", 0)
                                + hist.get(f"{c.v}-{u}", 0)
                            )
                        lines = [
                            f"Link: {u} <-> {c.v}",
                            f"Occupied: {occ} / {c.max_link_capacity}",
                        ]
                        break
                if lines:
                    break

        if lines:
            box = arcade.Text(
                "\n".join(lines),
                self.mouse_x + 16,
                self.mouse_y - 16,
                arcade.color.WHITE,
                11,
                multiline=True,
                width=240,
            )
            bw = box.content_width + 16
            bh = box.content_height + 16
            cx = self.mouse_x + 8 + bw / 2.0
            cy = self.mouse_y - 4 - bh / 2.0
            poly = (
                (cx - bw / 2.0, cy - bh / 2.0),
                (cx + bw / 2.0, cy - bh / 2.0),
                (cx + bw / 2.0, cy + bh / 2.0),
                (cx - bw / 2.0, cy + bh / 2.0),
            )
            arcade.draw_polygon_filled(
                poly, arcade.types.Color(20, 24, 30, 230)
            )
            arcade.draw_polygon_outline(poly, arcade.color.DARK_GRAY, 1)
            box.draw()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        """Saves current screen cursor coordinates."""
        self.mouse_x, self.mouse_y = float(x), float(y)

    def on_mouse_drag(
        self,
        x: int,
        y: int,
        dx: int,
        dy: int,
        buttons: int,
        modifiers: int,
    ) -> None:
        """Pans the world camera smoothly dividing delta by zoom level."""
        if buttons == arcade.MOUSE_BUTTON_LEFT:
            z = self.world_camera.zoom
            cx, cy = self.world_camera.position
            self.world_camera.position = (cx - dx / z, cy - dy / z)

    def on_mouse_scroll(
        self, x: int, y: int, scroll_x: float, scroll_y: float
    ) -> None:
        """Zooms centered on cursor using unprojected world coordinates."""
        if scroll_y != 0:
            factor = 1.12 if scroll_y > 0 else 1.0 / 1.12
            new_zoom = max(0.05, min(8.0, self.world_camera.zoom * factor))
            if new_zoom != self.world_camera.zoom:
                wb = self.world_camera.unproject((x, y))
                self.world_camera.zoom = new_zoom
                wa = self.world_camera.unproject((x, y))
                cx, cy = self.world_camera.position
                self.world_camera.position = (
                    cx + wb.x - wa.x,
                    cy + wb.y - wa.y,
                )

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Handles visualizer interactive hotkeys."""
        if symbol == arcade.key.SPACE:
            self.playing = not self.playing
        elif symbol == arcade.key.RIGHT:
            self.current_turn = min(
                float(self.max_turns), math.floor(self.current_turn) + 1.0
            )
        elif symbol == arcade.key.LEFT:
            self.current_turn = max(0.0, math.ceil(self.current_turn) - 1.0)
        elif symbol == arcade.key.R:
            self.current_turn, self.playing = 0.0, True
        elif symbol == arcade.key.F:
            self.world_camera.zoom = self.default_zoom
            self.world_camera.position = self.default_pos
        elif symbol == arcade.key.ESCAPE:
            arcade.close_window()
