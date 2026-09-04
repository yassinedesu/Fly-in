import arcade
from graph import Graph, ZoneType

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
SCREEN_TITLE = "Fly-in Drone Routing Visualizer"
MARGIN = 100

COLOR_MAP = {
    "green": arcade.color.GREEN, "red": arcade.color.RED,
    "blue": arcade.color.BLUE, "yellow": arcade.color.YELLOW,
    "orange": arcade.color.ORANGE, "purple": arcade.color.PURPLE,
    "gray": arcade.color.GRAY, "cyan": arcade.color.CYAN,
    "brown": arcade.color.BROWN, "magenta": arcade.color.MAGENTA,
    "lime": arcade.color.LIME_GREEN, "gold": arcade.color.GOLD,
    "black": arcade.color.BLACK
}

class FlyInVisualizer(arcade.Window):
    def __init__(self, graph: Graph, simulation_data: list[dict[str, str]] = None):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
        self.graph = graph
        arcade.set_background_color(arcade.color.SLATE_GRAY)
        
        self.simulation_data = simulation_data or []
        self.current_turn = 0
        self.max_turns = max(0, len(self.simulation_data) - 1)
        
        self.world_camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()
        
        # Adjusted to parse coordinates from your native graph.hubs dictionary
        xs = [hub.x for hub in graph.hubs.values()]
        ys = [hub.y for hub in graph.hubs.values()]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)

        self.ui_turn_text = arcade.Text(
            "", 10, 30, arcade.color.WHITE, 16, bold=True
        )
        self.ui_instruction_text = arcade.Text(
            "Press RIGHT/LEFT arrows to step through time | ESC to exit", 
            10, 10, arcade.color.WHITE, 12
        )

    def get_screen_coords(self, x: int, y: int) -> tuple[float, float]:
        range_x = max(1, self.max_x - self.min_x)
        range_y = max(1, self.max_y - self.min_y)
        screen_x = MARGIN + ((x - self.min_x) / range_x) * (SCREEN_WIDTH - 2 * MARGIN)
        screen_y = MARGIN + ((y - self.min_y) / range_y) * (SCREEN_HEIGHT - 2 * MARGIN)
        return screen_x, screen_y

    def on_key_press(self, key, modifiers):
        if key == arcade.key.RIGHT and self.current_turn < self.max_turns:
            self.current_turn += 1
        elif key == arcade.key.LEFT and self.current_turn > 0:
            self.current_turn -= 1
        elif key == arcade.key.ESCAPE:
            arcade.exit()

    def on_draw(self):
        self.clear()
        
        self.world_camera.use()
        drawn_edges = set()
        
        # Reverted to iterate over graph.adj and read edge.v 
        for u, edges in self.graph.adj.items():
            hub_u = self.graph.hubs[u]
            x1, y1 = self.get_screen_coords(hub_u.x, hub_u.y)
            for edge in edges:
                if frozenset([u, edge.v]) in drawn_edges:
                    continue
                drawn_edges.add(frozenset([u, edge.v]))
                hub_v = self.graph.hubs[edge.v]
                x2, y2 = self.get_screen_coords(hub_v.x, hub_v.y)
                arcade.draw_line(x1, y1, x2, y2, arcade.color.DARK_GRAY, 2)

        for hub in self.graph.hubs.values():
            cx, cy = self.get_screen_coords(hub.x, hub.y)
            base_color = COLOR_MAP.get(hub.color, arcade.color.LIGHT_BLUE) if hub.color else arcade.color.LIGHT_BLUE
            
            # Evaluates the ZoneType Enum natively
            if hub.zone == ZoneType.BLOCKED:
                base_color = arcade.color.BLACK
                
            arcade.draw_circle_filled(cx, cy, 20, base_color)
            arcade.draw_circle_outline(cx, cy, 20, arcade.color.BLACK, 2)
            arcade.Text(hub.name, cx - 20, cy + 25, arcade.color.WHITE, 12, bold=True).draw()

        if self.simulation_data:
            current_state = self.simulation_data[self.current_turn]
            for drone_id, location in current_state.items():
                if location in self.graph.hubs:
                    hub = self.graph.hubs[location]
                    cx, cy = self.get_screen_coords(hub.x, hub.y)
                    arcade.draw_circle_filled(cx, cy - 10, 8, arcade.color.WHITE)
                    arcade.draw_circle_outline(cx, cy - 10, 8, arcade.color.BLACK, 1)
                    arcade.Text(drone_id, cx - 6, cy - 14, arcade.color.BLACK, 8, bold=True).draw()
                
                elif "-" in location:
                    z1, z2 = location.split("-")
                    if z1 in self.graph.hubs and z2 in self.graph.hubs:
                        hub1, hub2 = self.graph.hubs[z1], self.graph.hubs[z2]
                        x1, y1 = self.get_screen_coords(hub1.x, hub1.y)
                        x2, y2 = self.get_screen_coords(hub2.x, hub2.y)
                        
                        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                        arcade.draw_circle_filled(cx, cy, 8, arcade.color.YELLOW)
                        arcade.draw_circle_outline(cx, cy, 8, arcade.color.BLACK, 1)
                        arcade.Text(drone_id, cx - 6, cy - 14, arcade.color.BLACK, 8, bold=True).draw()

        self.gui_camera.use()
        self.ui_turn_text.text = f"Turn: {self.current_turn} / {self.max_turns}"
        self.ui_turn_text.draw()
        self.ui_instruction_text.draw()