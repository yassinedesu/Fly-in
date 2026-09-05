"""Interactive hardware-accelerated visualizer for Fly-in drone routing."""

from __future__ import annotations
import colorsys
import math
import arcade
from graph import Graph, Hub, ZoneType

WINDOW_WIDTH: int = 1024
WINDOW_HEIGHT: int = 768
WINDOW_TITLE: str = "Fly-in Drone Routing Visualizer"

ZONE_RADIUS: float = 24.0
DRONE_RADIUS: float = 8.0
WORLD_SCALE: float = 140.0

MIN_ZOOM: float = 0.05
MAX_ZOOM: float = 8.0
ZOOM_STEP: float = 1.12

BACKGROUND_COLOR = arcade.color.EERIE_BLACK
LINE_COLOR = arcade.color.DARK_GRAY
TEXT_COLOR = arcade.color.WHITE

ZONE_TYPE_COLORS: dict[ZoneType, tuple[int, int, int]] = {
    ZoneType.NORMAL: arcade.color.LIGHT_GRAY,
    ZoneType.BLOCKED: arcade.color.DIM_GRAY,
    ZoneType.RESTRICTED: arcade.color.RED,
    ZoneType.PRIORITY: arcade.color.GREEN,
}

DRONE_COLORS: list[tuple[int, int, int]] = [
    arcade.color.YELLOW,
    arcade.color.CYAN,
    arcade.color.ORANGE,
    arcade.color.MAGENTA,
    arcade.color.SPRING_GREEN,
    arcade.color.PINK,
    arcade.color.SKY_BLUE,
    arcade.color.WHITE,
]


def get_rainbow_color(progress: float) -> tuple[int, int, int]:
    """Generates a dynamic RGB cycling hue for rainbow metadata tags."""
    r, g, b = colorsys.hsv_to_rgb((progress * 0.25) % 1.0, 0.85, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def resolve_hub_color(
    hub: Hub, graph: Graph, anim_time: float = 0.0
) -> tuple[int, int, int]:
    """Determines the color of a hub prioritizing metadata over defaults."""
    if hub.color:
        cleaned = hub.color.strip().upper()
        if cleaned == "RAINBOW":
            return get_rainbow_color(anim_time)

        # 1. Direct attribute match in arcade.color
        if hasattr(arcade.color, cleaned):
            val = getattr(arcade.color, cleaned)
            if isinstance(val, tuple) and len(val) >= 3:
                return val[:3]

        # 2. Check underscore normalized names
        normalized = cleaned.replace("-", "_").replace(" ", "_")
        if hasattr(arcade.color, normalized):
            val = getattr(arcade.color, normalized)
            if isinstance(val, tuple) and len(val) >= 3:
                return val[:3]

        # 3. Known extended map aliases
        aliases: dict[str, tuple[int, int, int]] = {
            "DARKRED": arcade.color.DARK_RED,
            "MAROON": arcade.color.MAROON,
            "CRIMSON": arcade.color.CRIMSON,
            "VIOLET": arcade.color.VIOLET,
            "GOLD": arcade.color.GOLD,
            "PURPLE": arcade.color.PURPLE,
            "LIME": arcade.color.LIME_GREEN,
            "CYAN": arcade.color.CYAN,
            "ORANGE": arcade.color.ORANGE,
            "GRAY": arcade.color.GRAY,
            "GREY": arcade.color.GRAY,
            "YELLOW": arcade.color.YELLOW,
            "BLUE": arcade.color.BLUE,
            "RED": arcade.color.RED,
            "GREEN": arcade.color.GREEN,
            "BLACK": arcade.color.BLACK,
            "WHITE": arcade.color.WHITE,
        }
        if normalized in aliases:
            return aliases[normalized]

    # Fallback to defaults if no custom color was specified
    if hub.is_start:
        return arcade.color.GREEN
    if hub.is_end:
        return arcade.color.GOLD

    return ZONE_TYPE_COLORS.get(hub.zone, arcade.color.LIGHT_GRAY)


def point_line_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    """Calculates point-to-segment distance via vector dot product."""
    px, py = p
    ax, ay = a
    bx, by = b

    vx, vy = bx - ax, by - ay
    length_sq = vx * vx + vy * vy
    if length_sq == 0.0:
        return math.hypot(px - ax, py - ay)

    # Algebraic dot product: (P - A) . (B - A) / |B - A|^2
    wx, wy = px - ax, py - ay
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / length_sq))
    proj_x = ax + t * vx
    proj_y = ay + t * vy
    return math.hypot(px - proj_x, py - proj_y)


class FlyInVisualizer(arcade.Window):
    """Dual-camera continuous visualizer with interpolation and tooltips."""

    def __init__(
        self,
        graph: Graph,
        simulation_data: list[dict[str, str]] | None = None,
        map_name: str = "",
    ) -> None:
        title = f"{WINDOW_TITLE} - {map_name}" if map_name else WINDOW_TITLE
        super().__init__(WINDOW_WIDTH, WINDOW_HEIGHT, title, fullscreen=False)
        self.graph = graph
        self.background_color = BACKGROUND_COLOR

        self.simulation_data = simulation_data or []
        self.max_turns: int = max(0, len(self.simulation_data) - 1)
        self.current_turn: float = 0.0
        self.playing: bool = True
        self.anim_speed: float = 2.0

        self.mouse_x: float = 0.0
        self.mouse_y: float = 0.0

        # World positions
        self.positions: dict[str, tuple[float, float]] = {
            hub.name: (float(hub.x * WORLD_SCALE), float(hub.y * WORLD_SCALE))
            for hub in self.graph.hubs.values()
        }

        # Drone color mapping
        self.drone_colors: dict[str, tuple[int, int, int]] = {
            f"D{i + 1}": DRONE_COLORS[i % len(DRONE_COLORS)]
            for i in range(self.graph.drone_count)
        }

        # Precompute per-turn drone coordinates
        end_name = self.graph.end_hub.name if self.graph.end_hub else ""
        self.drone_paths: dict[str, list[tuple[float, float]]] = {
            d_id: [] for d_id in self.drone_colors
        }

        for t in range(self.max_turns + 1):
            state = (
                self.simulation_data[t]
                if t < len(self.simulation_data)
                else {}
            )
            for d_id in self.drone_colors:
                loc = state.get(d_id, end_name)
                if "-" in loc:
                    z1, z2 = loc.split("-")
                    p1 = self.positions.get(z1, (0.0, 0.0))
                    p2 = self.positions.get(z2, (0.0, 0.0))
                    mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
                    self.drone_paths[d_id].append(mid)
                else:
                    self.drone_paths[d_id].append(
                        self.positions.get(loc, (0.0, 0.0))
                    )

        # Precompute occupancy lookup per turn
        self.occupancy_history: list[dict[str, int]] = []
        for t in range(self.max_turns + 1):
            state = (
                self.simulation_data[t]
                if t < len(self.simulation_data)
                else {}
            )
            occ: dict[str, int] = {}
            for loc in state.values():
                occ[loc] = occ.get(loc, 0) + 1
            self.occupancy_history.append(occ)

        # Dual cameras
        self.world_camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()

        self._fit_camera_view()

    def _fit_camera_view(self) -> None:
        """Centers and scales the camera to fit all network hubs."""
        if not self.positions:
            return

        xs = [pos[0] for pos in self.positions.values()]
        ys = [pos[1] for pos in self.positions.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        span_x = max(max_x - min_x + 220.0, 400.0)
        span_y = max(max_y - min_y + 220.0, 300.0)

        fit_zoom = min(WINDOW_WIDTH / span_x, WINDOW_HEIGHT / span_y)
        self.default_zoom = max(MIN_ZOOM, min(1.2, fit_zoom))
        self.default_pos = (center_x, center_y)

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
        """Renders world entities, lerped drones, and the GUI overlay."""
        self.clear()

        # 1. World Camera
        self.world_camera.use()

        # Check hovered connection
        world_mouse = self.world_camera.unproject((self.mouse_x, self.mouse_y))
        wx, wy = world_mouse.x, world_mouse.y

        hovered_edge: frozenset[str] | None = None
        drawn_connections: set[frozenset[str]] = set()

        for u, conns in self.graph.adj.items():
            p1 = self.positions[u]
            for conn in conns:
                pair = frozenset({u, conn.v})
                if pair in drawn_connections:
                    continue
                drawn_connections.add(pair)

                p2 = self.positions[conn.v]
                dist = point_line_distance((wx, wy), p1, p2)
                threshold = 12.0 / self.world_camera.zoom

                if dist <= threshold and hovered_edge is None:
                    hovered_edge = pair
                    arcade.draw_line(
                        p1[0], p1[1], p2[0], p2[1], arcade.color.YELLOW, 4
                    )
                else:
                    arcade.draw_line(
                        p1[0], p1[1], p2[0], p2[1], LINE_COLOR, 3
                    )

        # Draw Hubs
        for hub in self.graph.hubs.values():
            hx, hy = self.positions[hub.name]
            hub_col = resolve_hub_color(hub, self.graph, self.current_turn)

            arcade.draw_circle_filled(hx, hy, ZONE_RADIUS, hub_col)
            arcade.draw_circle_outline(
                hx, hy, ZONE_RADIUS, arcade.color.BLACK, 2
            )
            arcade.Text(
                hub.name,
                hx,
                hy + ZONE_RADIUS + 5,
                TEXT_COLOR,
                11,
                bold=True,
                anchor_x="center",
            ).draw()

        # Draw Drones with Linear Interpolation (Lerp)
        t0 = int(self.current_turn)
        t1 = min(t0 + 1, self.max_turns)
        progress = self.current_turn % 1.0 if t0 < self.max_turns else 0.0

        for d_id, path in self.drone_paths.items():
            if t0 >= len(path):
                continue
            p_start = path[t0]
            p_target = path[t1] if t1 < len(path) else p_start

            drone_x = p_start[0] + (p_target[0] - p_start[0]) * progress
            drone_y = p_start[1] + (p_target[1] - p_start[1]) * progress

            col = self.drone_colors.get(d_id, arcade.color.YELLOW)
            arcade.draw_circle_filled(drone_x, drone_y, DRONE_RADIUS, col)
            arcade.draw_circle_outline(
                drone_x, drone_y, DRONE_RADIUS, arcade.color.BLACK, 1.5
            )
            arcade.Text(
                d_id,
                drone_x,
                drone_y - 4,
                arcade.color.BLACK,
                8,
                bold=True,
                anchor_x="center",
            ).draw()

        # 2. GUI Camera
        self.gui_camera.use()
        self._draw_hud(t0)
        self._draw_tooltip(wx, wy, t0)

    def _draw_hud(self, current_whole_turn: int) -> None:
        """Renders fixed HUD counters and keyboard control guide."""
        end_name = self.graph.end_hub.name if self.graph.end_hub else ""
        delivered = (
            self.occupancy_history[current_whole_turn].get(end_name, 0)
            if current_whole_turn < len(self.occupancy_history)
            else 0
        )

        status_text = (
            f"Turn: {int(self.current_turn)} / {self.max_turns}   "
            f"Delivered: {delivered} / {self.graph.drone_count}"
        )
        arcade.Text(
            status_text,
            20,
            WINDOW_HEIGHT - 35,
            TEXT_COLOR,
            14,
            bold=True,
        ).draw()

        instructions = (
            "SPACE: Play/Pause | LEFT/RIGHT: Step | R: Restart | "
            "F: Reset View | Drag: Pan | Scroll: Zoom"
        )
        arcade.Text(
            instructions,
            20,
            18,
            arcade.color.GRAY,
            11,
        ).draw()

    def _draw_tooltip(self, wx: float, wy: float, t0: int) -> None:
        """Displays formatted metadata tooltips when hovering nodes/edges."""
        tooltip_lines: list[str] = []

        # Check Hub hover
        for hub in self.graph.hubs.values():
            hx, hy = self.positions[hub.name]
            if math.hypot(wx - hx, wy - hy) <= ZONE_RADIUS:
                occ = (
                    self.occupancy_history[t0].get(hub.name, 0)
                    if t0 < len(self.occupancy_history)
                    else 0
                )
                limit = (
                    self.graph.drone_count
                    if (hub.is_start or hub.is_end)
                    else hub.max_drones
                )
                color_tag = f" | Color: {hub.color}" if hub.color else ""
                tooltip_lines = [
                    f"Zone: {hub.name}",
                    f"Type: {hub.zone.value}{color_tag}",
                    f"Occupied: {occ} / {limit}",
                ]
                break

        # Check Connection hover
        if not tooltip_lines:
            for u, conns in self.graph.adj.items():
                p1 = self.positions[u]
                for conn in conns:
                    p2 = self.positions[conn.v]
                    threshold = 12.0 / self.world_camera.zoom
                    if point_line_distance((wx, wy), p1, p2) <= threshold:
                        c1 = f"{u}-{conn.v}"
                        c2 = f"{conn.v}-{u}"
                        occ = 0
                        if t0 < len(self.occupancy_history):
                            occ = (
                                self.occupancy_history[t0].get(c1, 0)
                                + self.occupancy_history[t0].get(c2, 0)
                            )
                        tooltip_lines = [
                            f"Link: {u} <-> {conn.v}",
                            f"Occupied: {occ} / {conn.max_link_capacity}",
                        ]
                        break
                if tooltip_lines:
                    break

        if tooltip_lines:
            content = "\n".join(tooltip_lines)
            box = arcade.Text(
                content,
                self.mouse_x + 16,
                self.mouse_y - 16,
                arcade.color.WHITE,
                11,
                multiline=True,
                width=240,
            )
            bw = box.content_width + 16
            bh = box.content_height + 16
            cx = self.mouse_x + 16 + bw / 2.0 - 4
            cy = self.mouse_y - 16 - bh / 2.0 + 12

            arcade.draw_polygon_filled(
                (
                    (cx - bw / 2.0, cy - bh / 2.0),
                    (cx + bw / 2.0, cy - bh / 2.0),
                    (cx + bw / 2.0, cy + bh / 2.0),
                    (cx - bw / 2.0, cy + bh / 2.0),
                ),
                (20, 24, 30, 230),
            )
            arcade.draw_polygon_outline(
                (
                    (cx - bw / 2.0, cy - bh / 2.0),
                    (cx + bw / 2.0, cy - bh / 2.0),
                    (cx + bw / 2.0, cy + bh / 2.0),
                    (cx - bw / 2.0, cy + bh / 2.0),
                ),
                arcade.color.DARK_GRAY,
                1,
            )
            box.draw()

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        self.mouse_x = float(x)
        self.mouse_y = float(y)

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
            factor = ZOOM_STEP if scroll_y > 0 else 1.0 / ZOOM_STEP
            new_zoom = max(
                MIN_ZOOM, min(MAX_ZOOM, self.world_camera.zoom * factor)
            )

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
            self.current_turn = 0.0
            self.playing = True
        elif symbol == arcade.key.F:
            self.world_camera.zoom = self.default_zoom
            self.world_camera.position = self.default_pos
        elif symbol == arcade.key.ESCAPE:
            arcade.close_window()