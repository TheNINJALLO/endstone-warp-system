"""
Endstone Warp System Plugin - Compatible with Endstone 0.11.8+
A complete warp management system for Minecraft Bedrock Edition

Author: Your Name
Version: 1.0.0
API Version: 0.5
"""

from endstone.plugin import Plugin
from endstone.event import event_handler, PlayerInteractEvent, PlayerQuitEvent
from endstone import Player, ColorFormat
from endstone.form import ActionForm, ModalForm, Dropdown, TextInput
from endstone.level import Location
import json
import time
from pathlib import Path
from typing import Dict, List, Any


class WarpSystemPlugin(Plugin):
    # Plugin metadata - NO YAML FILE NEEDED
    api_version = "0.11"

    # Plugin description
    description = "A comprehensive warp system with custom player warps and admin tools"

    def __init__(self):
        super().__init__()
        self.warp_db: Dict[str, Any] = {}
        self.cooldown_db: Dict[str, Any] = {}
        self.fixed_warps_db: Dict[str, Any] = {}
        self.bonus_slots_db: Dict[str, Any] = {}  # Track temporary bonus warp slots
        self.data_folder_path: Path = None
        self.interaction_cooldown: Dict[str, float] = {}  # Track interaction cooldowns
        self.players_with_forms: set = set()  # Track players who have forms open
        self.form_timestamps: Dict[str, float] = {}  # Track when forms were opened

        # Item to Minecraft native tag mapping
        self.warp_item_mapping = {
            "ninjos:rope1": "WARP1",
            "ninjos:rope2": "WARP2",
            "ninjos:rope3": "WARP3"
        }

        # Dimension display names
        self.dimension_names = {
            "minecraft:overworld": "Overworld",
            "minecraft:nether": "Nether",
            "minecraft:the_end": "End"
        }

    def on_load(self) -> None:
        """Called when the plugin is loaded"""
        self.logger.info(f"{ColorFormat.YELLOW}Warp System Plugin loading...")

    def on_enable(self) -> None:
        """Called when the plugin is enabled"""
        self.data_folder_path = Path(self.data_folder)
        self.data_folder_path.mkdir(parents=True, exist_ok=True)

        # Load databases
        self.load_database()

        # Register event listeners
        self.register_events(self)

        self.logger.info(f"{ColorFormat.GREEN}Warp System Plugin v1.2.2 enabled!")

    def on_disable(self) -> None:
        """Called when the plugin is disabled"""
        self.save_database()
        self.logger.info(f"{ColorFormat.RED}Warp System Plugin disabled!")

    def load_database(self) -> None:
        """Load warp and cooldown databases from JSON files"""
        warp_file = self.data_folder_path / "warps.json"
        cooldown_file = self.data_folder_path / "cooldowns.json"
        fixed_warps_file = self.data_folder_path / "fixed_warps.json"
        bonus_slots_file = self.data_folder_path / "bonus_slots.json"

        try:
            if warp_file.exists():
                with open(warp_file, 'r') as f:
                    self.warp_db = json.load(f)
            else:
                self.warp_db = {}

            if cooldown_file.exists():
                with open(cooldown_file, 'r') as f:
                    self.cooldown_db = json.load(f)
            else:
                self.cooldown_db = {}

            # Load fixed warps with defaults
            if fixed_warps_file.exists():
                with open(fixed_warps_file, 'r') as f:
                    self.fixed_warps_db = json.load(f)
            else:
                # Default fixed warps
                self.fixed_warps_db = {
                    "spawn": {
                        "name": "Spawn",
                        "coords": [438, 97, 757],
                        "dimension": "minecraft:overworld"
                    },
                    "shopping": {
                        "name": "Shopping District",
                        "coords": [411, 64, 184],
                        "dimension": "minecraft:overworld"
                    }
                }
                self.save_database()

            # Load bonus slots
            if bonus_slots_file.exists():
                with open(bonus_slots_file, 'r') as f:
                    self.bonus_slots_db = json.load(f)
            else:
                self.bonus_slots_db = {}

        except Exception as e:
            self.logger.error(f"Error loading databases: {e}")
            self.warp_db = {}
            self.cooldown_db = {}
            self.fixed_warps_db = {}
            self.bonus_slots_db = {}

    def save_database(self) -> None:
        """Save warp and cooldown databases to JSON files"""
        try:
            warp_file = self.data_folder_path / "warps.json"
            cooldown_file = self.data_folder_path / "cooldowns.json"
            fixed_warps_file = self.data_folder_path / "fixed_warps.json"
            bonus_slots_file = self.data_folder_path / "bonus_slots.json"

            with open(warp_file, 'w') as f:
                json.dump(self.warp_db, f, indent=2)

            with open(cooldown_file, 'w') as f:
                json.dump(self.cooldown_db, f, indent=2)

            with open(fixed_warps_file, 'w') as f:
                json.dump(self.fixed_warps_db, f, indent=2)

            with open(bonus_slots_file, 'w') as f:
                json.dump(self.bonus_slots_db, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving databases: {e}")

    @event_handler
    def on_player_interact(self, event: PlayerInteractEvent) -> None:
        """Handle player item interaction events"""
        player = event.player
        item = event.item

        if not player or not item:
            return

        # Check if this is a right-click action
        if event.action != PlayerInteractEvent.Action.RIGHT_CLICK_AIR and \
                event.action != PlayerInteractEvent.Action.RIGHT_CLICK_BLOCK:
            return

        # Get the item type ID (string identifier)
        item_type_id = item.type.id
        required_tag = self.warp_item_mapping.get(item_type_id)

        if not required_tag:
            return

        # Check interaction cooldown to prevent multiple forms opening
        player_name = player.name
        current_time = time.time()
        last_interaction = self.interaction_cooldown.get(player_name, 0)

        # 1 second cooldown between interactions
        if current_time - last_interaction < 1.0:
            return

        self.interaction_cooldown[player_name] = current_time

        # Clear stale form tracking for this player if it's been more than 5 seconds
        if player_name in self.form_timestamps:
            if current_time - self.form_timestamps[player_name] > 5:
                self.players_with_forms.discard(player_name)
                self.form_timestamps.pop(player_name, None)

        # Check if player has the required Minecraft native scoreboard tag OR Admin tag
        player_tags = player.scoreboard_tags
        if required_tag not in player_tags and "Admin" not in player_tags:
            player.send_message(f"{ColorFormat.RED}You need the Required Donation Privileges to use this item!")
            return

        # Show main menu
        self.show_main_menu(player)

    def clear_form_tracking(self, player_name: str = None):
        """Clear form tracking for a player or all players"""
        if player_name:
            self.players_with_forms.discard(player_name)
            self.form_timestamps.pop(player_name, None)
        else:
            self.players_with_forms.clear()
            self.form_timestamps.clear()

    def get_player_bonus_slots(self, player_name: str) -> int:
        """Get the number of active bonus slots for a player"""
        if player_name not in self.bonus_slots_db:
            return 0
        
        current_time = int(time.time() * 1000)
        total_bonus = 0
        active_bonuses = []
        
        for bonus in self.bonus_slots_db[player_name]:
            if bonus["expires_at"] > current_time:
                total_bonus += bonus["slots"]
                active_bonuses.append(bonus)
        
        # Clean up expired bonuses
        if len(active_bonuses) != len(self.bonus_slots_db[player_name]):
            self.bonus_slots_db[player_name] = active_bonuses
            if not active_bonuses:
                del self.bonus_slots_db[player_name]
            self.save_database()
        
        return total_bonus

    def debug_available_dimensions(self):
        """Debug method to log available dimensions"""
        try:
            level = self.server.level
            self.logger.info("=== DIMENSION DEBUG INFO ===")

            # Log level methods
            level_methods = [method for method in dir(level) if 'dimension' in method.lower()]
            self.logger.info(f"Level methods containing 'dimension': {level_methods}")

            # Try to get dimensions list
            if hasattr(level, 'dimensions'):
                try:
                    dimensions = level.dimensions
                    self.logger.info(f"Found {len(dimensions)} dimensions:")
                    for i, dim in enumerate(dimensions):
                        dim_name = getattr(dim, 'name', 'UNKNOWN')
                        dim_type = type(dim).__name__
                        self.logger.info(f"  {i}: {dim_name} (type: {dim_type})")
                except Exception as e:
                    self.logger.warning(f"Failed to list dimensions: {e}")

            self.logger.info("=== END DIMENSION DEBUG ===")
        except Exception as e:
            self.logger.error(f"Debug dimensions failed: {e}")

    @event_handler
    def on_player_quit(self, event: PlayerQuitEvent) -> None:
        """Handle player quit events to clean up form tracking"""
        player = event.player
        if player and player.name:
            # Clean up form tracking when player disconnects
            self.players_with_forms.discard(player.name)
            self.form_timestamps.pop(player.name, None)
            # Clean up interaction cooldown tracking
            self.interaction_cooldown.pop(player.name, None)

    def safe_send_form(self, player: Player, form) -> bool:
        """Safely send a form to a player, preventing multiple forms"""
        player_name = player.name
        current_time = time.time()

        # Clean up stale form tracking (forms older than 10 seconds)
        stale_players = []
        for tracked_player in list(self.players_with_forms):
            if tracked_player in self.form_timestamps:
                if current_time - self.form_timestamps[tracked_player] > 10:
                    stale_players.append(tracked_player)

        for stale_player in stale_players:
            self.players_with_forms.discard(stale_player)
            self.form_timestamps.pop(stale_player, None)

        # Check if player already has a form open
        if player_name in self.players_with_forms:
            # Give them one more chance - if it's been more than 2 seconds, clear it
            if player_name in self.form_timestamps and current_time - self.form_timestamps[player_name] > 2:
                self.players_with_forms.discard(player_name)
                self.form_timestamps.pop(player_name, None)
            else:
                # For now, let's be more permissive and allow the form anyway
                self.players_with_forms.discard(player_name)
                self.form_timestamps.pop(player_name, None)

        # Mark player as having a form open
        self.players_with_forms.add(player_name)
        self.form_timestamps[player_name] = current_time

        # Add close handler to remove player from tracking
        original_on_close = getattr(form, 'on_close', None)

        def safe_on_close(p):
            # Remove player from tracking when form closes
            self.players_with_forms.discard(p.name)
            self.form_timestamps.pop(p.name, None)
            # Call original close handler if it exists
            if original_on_close:
                original_on_close(p)

        form.on_close = safe_on_close

        # Send the form
        player.send_form(form)
        return True

    def has_tag(self, player: Player, tag: str) -> bool:
        """Check if player has a specific Minecraft scoreboard tag"""
        return tag in player.scoreboard_tags

    def get_player_warp_data(self, player: Player) -> Dict[str, Any]:
        """Get player's warp data and maximum custom warp slots"""
        player_name = player.name
        player_data = self.warp_db.get(player_name, {"customWarps": []})

        # Get player's scoreboard tags
        player_tags = player.scoreboard_tags

        # Determine max custom warps based on tags
        max_custom = 0
        if "WARP1" in player_tags:
            max_custom = 3
        if "WARP2" in player_tags:
            max_custom = 5
        if "WARP3" in player_tags:
            max_custom = 8
        if "Admin" in player_tags or "Owner" in player_tags:
            max_custom = float('inf')

        # Add bonus slots if player has any active ones
        if max_custom != float('inf'):
            bonus_slots = self.get_player_bonus_slots(player_name)
            max_custom += bonus_slots

        return {
            "playerName": player_name,
            "customWarps": player_data.get("customWarps", []),
            "maxCustom": max_custom
        }

    def show_main_menu(self, player: Player) -> None:
        """Display the main warp menu to the player"""
        try:
            warp_data = self.get_player_warp_data(player)
            custom_warps = warp_data["customWarps"]
            max_custom = warp_data["maxCustom"]

            form = ActionForm(title="Warp System")

            # Store warp references for button handling
            visible_warps = custom_warps[:len(custom_warps) if max_custom == float('inf') else int(max_custom)]

            # Add fixed warps dynamically from database
            for warp_key, warp_data in self.fixed_warps_db.items():
                display_dim = self.dimension_names.get(warp_data["dimension"], warp_data["dimension"])
                coords_str = " ".join(str(c) for c in warp_data["coords"])
                button_text = f"{warp_data['name']}\n§8{coords_str} - {display_dim}"
                form.add_button(button_text, "textures/items/ender_pearl",
                                lambda p, w=warp_data: self.teleport_to_location(p, w["coords"][0], w["coords"][1],
                                                                                 w["coords"][2], w["dimension"]))

            # Add custom warps
            for i, warp in enumerate(visible_warps):
                display_dim = self.dimension_names.get(warp["dimension"], warp["dimension"])
                coords_str = " ".join(str(c) for c in warp["coords"])
                button_text = f"{warp['name']}\n§8{coords_str} - {display_dim}"
                # Create closure to capture current warp data
                form.add_button(button_text, "textures/ui/World",
                                lambda p, w=warp, idx=i: self.show_warp_options(p, w, idx))

            # Add "New Warp" button if slots available
            if len(custom_warps) < max_custom:
                form.add_button("Add New Warp (+)\n§8Create a new warp point", "textures/ui/trade_icon",
                                lambda p: self.show_add_warp_form(p))

            # Admin buttons - check for Admin or Owner tags
            if self.has_tag(player, "Owner") or self.has_tag(player, "Admin"):
                form.add_button("Manage Fixed Warps\n§8Edit spawn & server warps", "textures/ui/op",
                                lambda p: self.show_manage_fixed_warps_menu(p))
                form.add_button("Manage Player Cooldowns\n§8Reset edit timers", "textures/ui/settings_glyph_color_2x",
                                lambda p: self.show_manage_cooldown_form(p))
                form.add_button("Grant Bonus Warp Slots\n§8Give temporary extra slots", "textures/ui/gift_square",
                                lambda p: self.show_grant_bonus_slots_form(p))
                form.add_button("View All Players' Warps\n§8Browse all warps", "textures/ui/FriendsDiversity",
                                lambda p: self.show_all_players_warps(p))

            if not self.safe_send_form(player, form):
                player.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_main_menu: {e}")
            player.send_message(f"{ColorFormat.RED}Error opening warp menu. Please try again.")

    def show_warp_options(self, player: Player, warp: Dict, index: int) -> None:
        """Show options for a specific warp"""
        try:
            form = ActionForm(title=warp["name"])

            # Teleport button
            form.add_button("Teleport\n§8Go to this warp", "textures/items/ender_pearl",
                            lambda p: self.handle_teleport_to_warp(p, warp))

            # Edit button
            form.add_button("Edit\n§8Modify warp details", "textures/ui/editIcon",
                            lambda p: self.handle_edit_warp(p, warp, index))

            # Delete button
            form.add_button("Delete\n§8Remove this warp", "textures/ui/trash",
                            lambda p: self.handle_delete_warp(p, warp, index))

            # Back button
            form.add_button("Back\n§8Return to main menu", "textures/ui/back_button",
                            lambda p: self.show_main_menu(p))

            if not self.safe_send_form(player, form):
                player.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_warp_options: {e}")
            player.send_message(f"{ColorFormat.RED}Error opening warp options.")

    def handle_teleport_to_warp(self, player: Player, warp: Dict) -> None:
        """Teleport player to a warp"""
        coords = warp["coords"]
        self.teleport_to_location(player, coords[0], coords[1], coords[2], warp["dimension"])

    def handle_edit_warp(self, player: Player, warp: Dict, index: int) -> None:
        """Handle edit warp with cooldown check"""
        if not self.check_cooldown(player):
            return
        self.show_edit_warp_form(player, warp, index)

    def handle_delete_warp(self, player: Player, warp: Dict, index: int) -> None:
        """Handle delete warp with cooldown check"""
        if not self.check_cooldown(player):
            return

        player_name = player.name
        warp_data = self.get_player_warp_data(player)
        warp_data["customWarps"].pop(index)
        self.warp_db[player_name] = {"customWarps": warp_data["customWarps"]}

        # Only apply cooldown if not Admin
        if not self.has_tag(player, "Admin"):
            self.cooldown_db[player_name] = {"lastEdit": int(time.time() * 1000)}

        self.save_database()
        player.send_message(f"{ColorFormat.RED}Deleted warp \"{warp['name']}\"")
        self.show_main_menu(player)

    def check_cooldown(self, player: Player) -> bool:
        """Check if player is on cooldown for editing/deleting warps"""
        # Admins bypass cooldown
        if self.has_tag(player, "Admin"):
            return True

        player_name = player.name
        last_edit = self.cooldown_db.get(player_name, {}).get("lastEdit", 0)
        cooldown_remaining = (6 * 60 * 60 * 1000) - (int(time.time() * 1000) - last_edit)

        if cooldown_remaining > 0:
            minutes = cooldown_remaining // (60 * 1000)
            player.send_message(
                f"{ColorFormat.RED}You can only edit/delete warps every 6 hours. Please wait {minutes} more minutes.")
            return False
        return True

    def show_add_warp_form(self, player: Player) -> None:
        """Show form to add a new warp"""
        try:
            form = ModalForm(title="Add New Warp")

            form.add_control(TextInput(
                label="Warp Name (max 15 chars)",
                placeholder="Enter name..."
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=0
            ))
            form.add_control(TextInput(
                label="Coordinates (optional)",
                placeholder="x y z - Leave blank for current position"
            ))

            def on_submit(p: Player, data: str):
                try:
                    # Parse JSON response from modal form
                    response = json.loads(data)

                    name = response[0][:15].strip()
                    dimension_index = response[1]
                    coords_str = response[2]

                    if not name:
                        p.send_message(f"{ColorFormat.RED}Please enter a name for your warp!")
                        return

                    warp_data = self.get_player_warp_data(p)
                    dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]

                    if coords_str.strip():
                        # Parse custom coordinates
                        coords = [int(x) for x in coords_str.split() if x.strip().lstrip('-').isdigit()]
                        if len(coords) != 3:
                            p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                            return
                        dimension = dimension_map[dimension_index]
                    else:
                        # Use current position
                        loc = p.location
                        coords = [int(loc.x), int(loc.y), int(loc.z)]
                        # Get dimension name from player's current dimension
                        dim_name = p.dimension.name
                        # Keep the full dimension name (minecraft:overworld format)
                        dimension = dim_name

                    warp_data["customWarps"].append({
                        "name": name,
                        "coords": coords,
                        "dimension": dimension
                    })

                    self.warp_db[p.name] = {"customWarps": warp_data["customWarps"]}
                    self.save_database()

                    display_dim = self.dimension_names.get(dimension, dimension)
                    coords_str = " ".join(str(c) for c in coords)
                    p.send_message(f"{ColorFormat.GREEN}Added new warp: {name} at {coords_str} in {display_dim}")
                    self.show_main_menu(p)
                except Exception as e:
                    self.logger.error(f"Error in add warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error adding warp: {str(e)}")

            form.on_submit = on_submit

            if not self.safe_send_form(player, form):
                player.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_add_warp_form: {e}")
            player.send_message(f"{ColorFormat.RED}Error opening add warp form.")

    def show_edit_warp_form(self, player: Player, warp: Dict, index: int) -> None:
        """Show form to edit an existing warp"""
        try:
            dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]
            current_dim_index = dimension_map.index(warp["dimension"]) if warp["dimension"] in dimension_map else 0

            form = ModalForm(title="Edit Warp")

            form.add_control(TextInput(
                label="Warp Name",
                placeholder="New name...",
                default_value=warp["name"]
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=current_dim_index
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z",
                default_value=" ".join(str(c) for c in warp["coords"])
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    new_name = response[0][:15].strip()
                    new_dim_index = response[1]
                    new_coords_str = response[2]

                    if not new_name:
                        p.send_message(f"{ColorFormat.RED}Warp name cannot be empty!")
                        return

                    new_coords = [int(x) for x in new_coords_str.split() if x.strip().lstrip('-').isdigit()]
                    if len(new_coords) != 3:
                        p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                        return

                    warp_data = self.get_player_warp_data(p)
                    new_dimension = dimension_map[new_dim_index]

                    warp_data["customWarps"][index] = {
                        "name": new_name,
                        "coords": new_coords,
                        "dimension": new_dimension
                    }

                    self.warp_db[p.name] = {"customWarps": warp_data["customWarps"]}

                    # Apply cooldown if not Admin
                    if not self.has_tag(p, "Admin"):
                        self.cooldown_db[p.name] = {"lastEdit": int(time.time() * 1000)}

                    self.save_database()

                    display_dim = self.dimension_names.get(new_dimension, new_dimension)
                    coords_str = " ".join(str(c) for c in new_coords)
                    p.send_message(f"{ColorFormat.GREEN}Updated warp: {new_name} at {coords_str} in {display_dim}")
                    self.show_main_menu(p)
                except Exception as e:
                    self.logger.error(f"Error in edit warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error updating warp: {str(e)}")

            form.on_submit = on_submit

            if not self.safe_send_form(player, form):
                player.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_edit_warp_form: {e}")
            player.send_message(f"{ColorFormat.RED}Error opening edit warp form.")

    def show_manage_cooldown_form(self, admin: Player) -> None:
        """Show form to manage player cooldowns (admin only)"""
        try:
            form = ModalForm(title="Manage Player Cooldowns")

            form.add_control(TextInput(
                label="Enter player name to reset cooldown",
                placeholder="Player name"
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)
                    target_player_name = response[0].strip()

                    if not target_player_name:
                        p.send_message(f"{ColorFormat.RED}Please enter a player name.")
                        return

                    if target_player_name in self.cooldown_db:
                        del self.cooldown_db[target_player_name]
                        self.save_database()

                    p.send_message(f"{ColorFormat.GREEN}Edit cooldown reset for player {target_player_name}.")
                except Exception as e:
                    self.logger.error(f"Error in cooldown form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error resetting cooldown")

            form.on_submit = on_submit

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_manage_cooldown_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening cooldown management form.")

    def show_grant_bonus_slots_form(self, admin: Player) -> None:
        """Show form to grant temporary bonus warp slots to a player (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            form = ModalForm(title="Grant Bonus Warp Slots")

            form.add_control(TextInput(
                label="Player Name",
                placeholder="Enter player name..."
            ))
            form.add_control(TextInput(
                label="Number of Extra Slots",
                placeholder="e.g., 2",
                default_value="1"
            ))
            form.add_control(Dropdown(
                label="Duration",
                options=["1 Hour", "6 Hours", "12 Hours", "1 Day", "3 Days", "7 Days", "14 Days", "30 Days", "Permanent (365 days)"],
                default_index=3
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    target_player_name = response[0].strip()
                    slots_str = response[1].strip()
                    duration_index = response[2]

                    if not target_player_name:
                        p.send_message(f"{ColorFormat.RED}Please enter a player name!")
                        return

                    try:
                        slots = int(slots_str)
                        if slots < 1 or slots > 10:
                            p.send_message(f"{ColorFormat.RED}Slots must be between 1 and 10!")
                            return
                    except ValueError:
                        p.send_message(f"{ColorFormat.RED}Invalid number of slots!")
                        return

                    # Duration in milliseconds
                    duration_map = {
                        0: 1 * 60 * 60 * 1000,         # 1 hour
                        1: 6 * 60 * 60 * 1000,         # 6 hours
                        2: 12 * 60 * 60 * 1000,        # 12 hours
                        3: 24 * 60 * 60 * 1000,        # 1 day
                        4: 3 * 24 * 60 * 60 * 1000,    # 3 days
                        5: 7 * 24 * 60 * 60 * 1000,    # 7 days
                        6: 14 * 24 * 60 * 60 * 1000,   # 14 days
                        7: 30 * 24 * 60 * 60 * 1000,   # 30 days
                        8: 365 * 24 * 60 * 60 * 1000,  # 365 days (permanent)
                    }
                    duration_names = ["1 hour", "6 hours", "12 hours", "1 day", "3 days", "7 days", "14 days", "30 days", "365 days"]

                    duration_ms = duration_map.get(duration_index, 24 * 60 * 60 * 1000)
                    current_time = int(time.time() * 1000)
                    expires_at = current_time + duration_ms

                    # Add bonus to player's record
                    if target_player_name not in self.bonus_slots_db:
                        self.bonus_slots_db[target_player_name] = []

                    self.bonus_slots_db[target_player_name].append({
                        "slots": slots,
                        "expires_at": expires_at,
                        "granted_by": p.name,
                        "granted_at": current_time
                    })

                    self.save_database()

                    duration_name = duration_names[duration_index]
                    p.send_message(f"{ColorFormat.GREEN}Granted {slots} bonus warp slot{'s' if slots > 1 else ''} to {target_player_name} for {duration_name}!")
                    
                    # Notify target player if online
                    target = self.server.get_player(target_player_name)
                    if target:
                        target.send_message(f"{ColorFormat.GREEN}You have been granted {slots} bonus warp slot{'s' if slots > 1 else ''} for {duration_name}!")

                except Exception as e:
                    self.logger.error(f"Error in grant bonus slots form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error granting bonus slots: {str(e)}")

            form.on_submit = on_submit

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_grant_bonus_slots_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening bonus slots form.")

    def show_all_players_warps(self, player: Player) -> None:
        """Show menu to select a player to manage their warps (admin only)"""
        if not self.has_tag(player, "Owner") and not self.has_tag(player, "Admin"):
            return

        try:
            form = ActionForm(title="Manage Player Warps")
            form.content = "Select a player to manage their warps, or add a warp for a new player."

            # Get list of players who have warps
            players_with_warps = []
            for player_name, data in self.warp_db.items():
                custom_warps = data.get("customWarps", [])
                if custom_warps:
                    players_with_warps.append((player_name, len(custom_warps)))

            # Add button for each player with warps
            for pname, warp_count in sorted(players_with_warps, key=lambda x: x[0].lower()):
                button_text = f"{pname}\n§8{warp_count} warp{'s' if warp_count != 1 else ''}"
                form.add_button(button_text, "textures/ui/FriendsDiversity",
                                lambda p, name=pname: self.show_player_warps_management(p, name))

            # Add warp for any player (by name input)
            form.add_button("Add Warp for Player\n§8Create warp for any player", "textures/ui/color_plus",
                            lambda p: self.show_add_warp_for_player_form(p))

            # Back button
            form.add_button("Back\n§8Return to main menu", "textures/ui/back_button",
                            lambda p: self.show_main_menu(p))

            if not self.safe_send_form(player, form):
                player.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_all_players_warps: {e}")
            player.send_message(f"{ColorFormat.RED}Error: {str(e)}")

    def show_player_warps_management(self, admin: Player, target_player_name: str) -> None:
        """Show management options for a specific player's warps (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            player_data = self.warp_db.get(target_player_name, {"customWarps": []})
            custom_warps = player_data.get("customWarps", [])

            form = ActionForm(title=f"Manage {target_player_name}'s Warps")

            if not custom_warps:
                form.content = f"{target_player_name} has no warps."
            else:
                form.content = f"Select a warp to manage or add a new one."

            # Add button for each warp
            for i, warp in enumerate(custom_warps):
                display_dim = self.dimension_names.get(warp["dimension"], warp["dimension"])
                coords_str = " ".join(str(c) for c in warp["coords"])
                button_text = f"{warp['name']}\n§8{coords_str} - {display_dim}"
                form.add_button(button_text, "textures/ui/World",
                                lambda p, w=warp, idx=i, tpn=target_player_name: self.show_player_warp_options(p, tpn, w, idx))

            # Add new warp for this player
            form.add_button("Add New Warp\n§8Create warp for this player", "textures/ui/color_plus",
                            lambda p, tpn=target_player_name: self.show_add_warp_for_specific_player(p, tpn))

            # Back button
            form.add_button("Back\n§8Return to player list", "textures/ui/back_button",
                            lambda p: self.show_all_players_warps(p))

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_player_warps_management: {e}")
            admin.send_message(f"{ColorFormat.RED}Error: {str(e)}")

    def show_player_warp_options(self, admin: Player, target_player_name: str, warp: Dict, index: int) -> None:
        """Show options for a specific player's warp (teleport, edit, delete)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            display_dim = self.dimension_names.get(warp["dimension"], warp["dimension"])
            coords_str = " ".join(str(c) for c in warp["coords"])

            form = ActionForm(title=f"{target_player_name}'s {warp['name']}")
            form.content = f"Location: {coords_str} in {display_dim}"

            # Teleport button
            form.add_button("Teleport\n§8Go to this warp", "textures/items/ender_pearl",
                            lambda p, w=warp: self.handle_teleport_to_warp(p, w))

            # Edit button
            form.add_button("Edit\n§8Modify warp details", "textures/ui/editIcon",
                            lambda p, tpn=target_player_name, w=warp, idx=index: self.show_edit_player_warp_form(p, tpn, w, idx))

            # Delete button
            form.add_button("Delete\n§8Remove this warp", "textures/ui/trash",
                            lambda p, tpn=target_player_name, w=warp, idx=index: self.confirm_delete_player_warp(p, tpn, w, idx))

            # Back button
            form.add_button("Back\n§8Return to player's warps", "textures/ui/back_button",
                            lambda p, tpn=target_player_name: self.show_player_warps_management(p, tpn))

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_player_warp_options: {e}")
            admin.send_message(f"{ColorFormat.RED}Error: {str(e)}")

    def show_add_warp_for_player_form(self, admin: Player) -> None:
        """Show form to add a warp for any player by name (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            form = ModalForm(title="Add Warp for Player")

            form.add_control(TextInput(
                label="Player Name",
                placeholder="Enter player name..."
            ))
            form.add_control(TextInput(
                label="Warp Name (max 15 chars)",
                placeholder="Enter warp name..."
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=0
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z - or leave blank for your position"
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    target_player_name = response[0].strip()
                    warp_name = response[1][:15].strip()
                    dimension_index = response[2]
                    coords_str = response[3]

                    if not target_player_name:
                        p.send_message(f"{ColorFormat.RED}Please enter a player name!")
                        return

                    if not warp_name:
                        p.send_message(f"{ColorFormat.RED}Please enter a warp name!")
                        return

                    dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]

                    if coords_str.strip():
                        coords = [int(x) for x in coords_str.split() if x.strip().lstrip('-').isdigit()]
                        if len(coords) != 3:
                            p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                            return
                        dimension = dimension_map[dimension_index]
                    else:
                        loc = p.location
                        coords = [int(loc.x), int(loc.y), int(loc.z)]
                        dim_name = p.dimension.name
                        dimension = dim_name

                    # Get or create player data
                    player_data = self.warp_db.get(target_player_name, {"customWarps": []})
                    custom_warps = player_data.get("customWarps", [])

                    custom_warps.append({
                        "name": warp_name,
                        "coords": coords,
                        "dimension": dimension
                    })

                    self.warp_db[target_player_name] = {"customWarps": custom_warps}
                    self.save_database()

                    display_dim = self.dimension_names.get(dimension, dimension)
                    coords_display = " ".join(str(c) for c in coords)
                    p.send_message(f"{ColorFormat.GREEN}Added warp '{warp_name}' for {target_player_name} at {coords_display} in {display_dim}")
                    self.show_player_warps_management(p, target_player_name)

                except Exception as e:
                    self.logger.error(f"Error in add warp for player form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error adding warp: {str(e)}")

            form.on_submit = on_submit
            form.on_close = lambda p: self.show_all_players_warps(p)

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_add_warp_for_player_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening add warp form.")

    def show_add_warp_for_specific_player(self, admin: Player, target_player_name: str) -> None:
        """Show form to add a new warp for a specific player (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            form = ModalForm(title=f"Add Warp for {target_player_name}")

            form.add_control(TextInput(
                label="Warp Name (max 15 chars)",
                placeholder="Enter warp name..."
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=0
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z - or leave blank for your position"
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    warp_name = response[0][:15].strip()
                    dimension_index = response[1]
                    coords_str = response[2]

                    if not warp_name:
                        p.send_message(f"{ColorFormat.RED}Please enter a warp name!")
                        return

                    dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]

                    if coords_str.strip():
                        coords = [int(x) for x in coords_str.split() if x.strip().lstrip('-').isdigit()]
                        if len(coords) != 3:
                            p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                            return
                        dimension = dimension_map[dimension_index]
                    else:
                        loc = p.location
                        coords = [int(loc.x), int(loc.y), int(loc.z)]
                        dim_name = p.dimension.name
                        dimension = dim_name

                    # Get or create player data
                    player_data = self.warp_db.get(target_player_name, {"customWarps": []})
                    custom_warps = player_data.get("customWarps", [])

                    custom_warps.append({
                        "name": warp_name,
                        "coords": coords,
                        "dimension": dimension
                    })

                    self.warp_db[target_player_name] = {"customWarps": custom_warps}
                    self.save_database()

                    display_dim = self.dimension_names.get(dimension, dimension)
                    coords_display = " ".join(str(c) for c in coords)
                    p.send_message(f"{ColorFormat.GREEN}Added warp '{warp_name}' for {target_player_name} at {coords_display} in {display_dim}")
                    self.show_player_warps_management(p, target_player_name)

                except Exception as e:
                    self.logger.error(f"Error in add warp for specific player form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error adding warp: {str(e)}")

            form.on_submit = on_submit
            form.on_close = lambda p, tpn=target_player_name: self.show_player_warps_management(p, tpn)

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_add_warp_for_specific_player: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening add warp form.")

    def show_edit_player_warp_form(self, admin: Player, target_player_name: str, warp: Dict, index: int) -> None:
        """Show form to edit a player's warp (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]
            current_dim_index = dimension_map.index(warp["dimension"]) if warp["dimension"] in dimension_map else 0

            form = ModalForm(title=f"Edit {target_player_name}'s Warp")

            form.add_control(TextInput(
                label="Warp Name",
                placeholder="New name...",
                default_value=warp["name"]
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=current_dim_index
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z",
                default_value=" ".join(str(c) for c in warp["coords"])
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    new_name = response[0][:15].strip()
                    new_dim_index = response[1]
                    new_coords_str = response[2]

                    if not new_name:
                        p.send_message(f"{ColorFormat.RED}Warp name cannot be empty!")
                        return

                    new_coords = [int(x) for x in new_coords_str.split() if x.strip().lstrip('-').isdigit()]
                    if len(new_coords) != 3:
                        p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                        return

                    new_dimension = dimension_map[new_dim_index]

                    # Update the warp
                    player_data = self.warp_db.get(target_player_name, {"customWarps": []})
                    custom_warps = player_data.get("customWarps", [])

                    if index < len(custom_warps):
                        custom_warps[index] = {
                            "name": new_name,
                            "coords": new_coords,
                            "dimension": new_dimension
                        }
                        self.warp_db[target_player_name] = {"customWarps": custom_warps}
                        self.save_database()

                        display_dim = self.dimension_names.get(new_dimension, new_dimension)
                        coords_str = " ".join(str(c) for c in new_coords)
                        p.send_message(f"{ColorFormat.GREEN}Updated {target_player_name}'s warp: {new_name} at {coords_str} in {display_dim}")
                    else:
                        p.send_message(f"{ColorFormat.RED}Error: Warp not found!")

                    self.show_player_warps_management(p, target_player_name)

                except Exception as e:
                    self.logger.error(f"Error in edit player warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error updating warp: {str(e)}")

            form.on_submit = on_submit
            form.on_close = lambda p, tpn=target_player_name: self.show_player_warps_management(p, tpn)

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_edit_player_warp_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening edit warp form.")

    def confirm_delete_player_warp(self, admin: Player, target_player_name: str, warp: Dict, index: int) -> None:
        """Confirm deletion of a player's warp (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            form = ActionForm(title="Confirm Delete")
            form.content = f"Are you sure you want to delete {target_player_name}'s warp \"{warp['name']}\"?\n\nThis action cannot be undone."

            # Confirm delete button
            form.add_button("Delete\n§cConfirm deletion", "textures/ui/trash",
                            lambda p, tpn=target_player_name, w=warp, idx=index: self.delete_player_warp(p, tpn, w, idx))

            # Cancel button
            form.add_button("Cancel\n§8Keep the warp", "textures/ui/back_button",
                            lambda p, tpn=target_player_name, w=warp, idx=index: self.show_player_warp_options(p, tpn, w, idx))

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in confirm_delete_player_warp: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening confirmation form.")

    def delete_player_warp(self, admin: Player, target_player_name: str, warp: Dict, index: int) -> None:
        """Delete a player's warp (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            player_data = self.warp_db.get(target_player_name, {"customWarps": []})
            custom_warps = player_data.get("customWarps", [])

            if index < len(custom_warps):
                deleted_warp = custom_warps.pop(index)
                self.warp_db[target_player_name] = {"customWarps": custom_warps}

                # Clean up empty player entries
                if not custom_warps:
                    del self.warp_db[target_player_name]

                self.save_database()
                admin.send_message(f"{ColorFormat.RED}Deleted {target_player_name}'s warp \"{deleted_warp['name']}\"")
            else:
                admin.send_message(f"{ColorFormat.RED}Error: Warp not found!")

            # Go back to player's warps list (or player list if no warps left)
            if custom_warps:
                self.show_player_warps_management(admin, target_player_name)
            else:
                self.show_all_players_warps(admin)

        except Exception as e:
            self.logger.error(f"Error in delete_player_warp: {e}")
            admin.send_message(f"{ColorFormat.RED}Error deleting warp: {str(e)}")

    def show_manage_fixed_warps_menu(self, admin: Player) -> None:
        """Show menu to manage fixed server warps (admin only)"""
        if not self.has_tag(admin, "Owner") and not self.has_tag(admin, "Admin"):
            return

        try:
            form = ActionForm(title="Manage Fixed Warps")

            # Add button for each fixed warp
            for warp_key, warp_data in self.fixed_warps_db.items():
                display_dim = self.dimension_names.get(warp_data["dimension"], warp_data["dimension"])
                coords_str = " ".join(str(c) for c in warp_data["coords"])
                button_text = f"Edit: {warp_data['name']}\n§8{coords_str} - {display_dim}"
                form.add_button(button_text, "textures/ui/editIcon",
                                lambda p, key=warp_key: self.show_edit_fixed_warp_form(p, key))

            # Add new fixed warp button
            form.add_button("Add New Fixed Warp\n§8Create server warp", "textures/ui/color_plus",
                            lambda p: self.show_add_fixed_warp_form(p))

            # Back button
            form.add_button("Back\n§8Return to main menu", "textures/ui/back_button",
                            lambda p: self.show_main_menu(p))

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_manage_fixed_warps_menu: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening fixed warps menu.")

    def show_add_fixed_warp_form(self, admin: Player) -> None:
        """Show form to add a new fixed warp (admin only)"""
        try:
            form = ModalForm(title="Add New Fixed Warp")

            form.add_control(TextInput(
                label="Warp Key (internal identifier)",
                placeholder="e.g., pvp_arena"
            ))
            form.add_control(TextInput(
                label="Display Name",
                placeholder="e.g., PvP Arena"
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=0
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z - or leave blank for current position"
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    warp_key = response[0].strip().lower().replace(" ", "_")
                    display_name = response[1].strip()
                    dimension_index = response[2]
                    coords_str = response[3]

                    if not warp_key or not display_name:
                        p.send_message(f"{ColorFormat.RED}Please enter both key and name!")
                        return

                    if warp_key in self.fixed_warps_db:
                        p.send_message(f"{ColorFormat.RED}A fixed warp with key '{warp_key}' already exists!")
                        return

                    dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]

                    if coords_str.strip():
                        coords = [int(x) for x in coords_str.split() if x.strip().lstrip('-').isdigit()]
                        if len(coords) != 3:
                            p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                            return
                    else:
                        loc = p.location
                        coords = [int(loc.x), int(loc.y), int(loc.z)]

                    dimension = dimension_map[dimension_index]

                    self.fixed_warps_db[warp_key] = {
                        "name": display_name,
                        "coords": coords,
                        "dimension": dimension
                    }

                    self.save_database()

                    display_dim = self.dimension_names.get(dimension, dimension)
                    coords_str = " ".join(str(c) for c in coords)
                    p.send_message(
                        f"{ColorFormat.GREEN}Added fixed warp: {display_name} at {coords_str} in {display_dim}")
                    self.show_manage_fixed_warps_menu(p)

                except Exception as e:
                    self.logger.error(f"Error in add fixed warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error adding fixed warp: {str(e)}")

            form.on_submit = on_submit
            form.on_close = lambda p: self.show_manage_fixed_warps_menu(p)

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_add_fixed_warp_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening add fixed warp form.")

    def show_edit_fixed_warp_form(self, admin: Player, warp_key: str) -> None:
        """Show form to edit a fixed warp (admin only)"""
        try:
            warp = self.fixed_warps_db.get(warp_key)
            if not warp:
                admin.send_message(f"{ColorFormat.RED}Fixed warp not found!")
                return

            dimension_map = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]
            current_dim_index = dimension_map.index(warp["dimension"]) if warp["dimension"] in dimension_map else 0

            form = ModalForm(title=f"Edit: {warp['name']}")

            form.add_control(TextInput(
                label="Display Name",
                placeholder="New name...",
                default_value=warp["name"]
            ))
            form.add_control(Dropdown(
                label="Dimension",
                options=["Overworld", "Nether", "End"],
                default_index=current_dim_index
            ))
            form.add_control(TextInput(
                label="Coordinates",
                placeholder="x y z",
                default_value=" ".join(str(c) for c in warp["coords"])
            ))

            def on_submit(p: Player, data: str):
                try:
                    response = json.loads(data)

                    new_name = response[0].strip()
                    new_dim_index = response[1]
                    new_coords_str = response[2]

                    if not new_name:
                        p.send_message(f"{ColorFormat.RED}Warp name cannot be empty!")
                        return

                    new_coords = [int(x) for x in new_coords_str.split() if x.strip().lstrip('-').isdigit()]
                    if len(new_coords) != 3:
                        p.send_message(f"{ColorFormat.RED}Invalid coordinates! Use whole numbers like '100 64 200'")
                        return

                    new_dimension = dimension_map[new_dim_index]

                    self.fixed_warps_db[warp_key] = {
                        "name": new_name,
                        "coords": new_coords,
                        "dimension": new_dimension
                    }

                    self.save_database()

                    display_dim = self.dimension_names.get(new_dimension, new_dimension)
                    coords_str = " ".join(str(c) for c in new_coords)
                    p.send_message(
                        f"{ColorFormat.GREEN}Updated fixed warp: {new_name} at {coords_str} in {display_dim}")
                    self.show_manage_fixed_warps_menu(p)

                except Exception as e:
                    self.logger.error(f"Error in edit fixed warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error updating fixed warp: {str(e)}")

            # Add delete option
            form.add_control(TextInput(
                label="Type 'DELETE' to remove this warp",
                placeholder="Leave blank to keep"
            ))

            def on_submit_with_delete(p: Player, data: str):
                try:
                    response = json.loads(data)
                    delete_confirm = response[3].strip().upper()

                    if delete_confirm == "DELETE":
                        del self.fixed_warps_db[warp_key]
                        self.save_database()
                        p.send_message(f"{ColorFormat.RED}Deleted fixed warp: {warp['name']}")
                        self.show_manage_fixed_warps_menu(p)
                    else:
                        on_submit(p, data)

                except Exception as e:
                    self.logger.error(f"Error in edit fixed warp form submission: {e}")
                    p.send_message(f"{ColorFormat.RED}Error updating fixed warp: {str(e)}")

            form.on_submit = on_submit_with_delete
            form.on_close = lambda p: self.show_manage_fixed_warps_menu(p)

            if not self.safe_send_form(admin, form):
                admin.send_message(f"{ColorFormat.YELLOW}Please close your current form first.")

        except Exception as e:
            self.logger.error(f"Error in show_edit_fixed_warp_form: {e}")
            admin.send_message(f"{ColorFormat.RED}Error opening edit fixed warp form.")

    def teleport_to_location(self, player: Player, x: int, y: int, z: int, dimension_id: str) -> None:
        """Teleport player to specified coordinates and dimension"""
        try:
            # Normalize dimension ID to full minecraft: format
            dimension_map = {
                "overworld": "minecraft:overworld",
                "nether": "minecraft:nether",
                "the_end": "minecraft:the_end",
                "minecraft:overworld": "minecraft:overworld",
                "minecraft:nether": "minecraft:nether",
                "minecraft:the_end": "minecraft:the_end"
            }

            # Get the proper dimension name
            proper_dimension_id = dimension_map.get(dimension_id, dimension_id)

            # Get player's current dimension name
            player_dim_name = getattr(player.dimension, 'name', None) if hasattr(player, 'dimension') else None

            # Normalize player dimension name for comparison
            player_dim_normalized = player_dim_name
            if player_dim_name and not player_dim_name.startswith("minecraft:"):
                # Convert short names to full format for comparison
                short_to_full = {
                    "Overworld": "minecraft:overworld",
                    "Nether": "minecraft:nether",
                    "End": "minecraft:the_end",
                    "TheEnd": "minecraft:the_end"
                }
                player_dim_normalized = short_to_full.get(player_dim_name, f"minecraft:{player_dim_name.lower()}")

            if player_dim_normalized == proper_dimension_id:
                # Same dimension - just create new location with same dimension
                dimension = player.dimension
            else:
                # Different dimension - need to get the target dimension
                dimension = None
                level = self.server.level

                # Try multiple approaches to get the target dimension
                dimension_methods = [
                    ('get_dimension', lambda l, d: l.get_dimension(d)),
                    ('getDimension', lambda l, d: l.getDimension(d)),
                ]

                # Try different dimension name formats
                dimension_name_variants = [
                    proper_dimension_id,
                    proper_dimension_id.replace('minecraft:', ''),
                    proper_dimension_id.replace('minecraft:', '').title(),
                ]

                # Special case for "the_end"
                if 'the_end' in proper_dimension_id:
                    dimension_name_variants.extend(['TheEnd', 'End', 'the_end'])

                for method_name, method_func in dimension_methods:
                    if hasattr(level, method_name):
                        for variant in dimension_name_variants:
                            try:
                                dimension = method_func(level, variant)
                                if dimension:
                                    break
                            except Exception:
                                pass
                        if dimension:
                            break

                # If we still don't have the dimension, try to find it in the dimensions list
                if dimension is None:
                    try:
                        if hasattr(level, 'dimensions'):
                            dimensions = level.dimensions
                            for dim in dimensions:
                                dim_name = getattr(dim, 'name', None)
                                if dim_name == proper_dimension_id or dim_name == proper_dimension_id.replace('minecraft:', ''):
                                    dimension = dim
                                    break
                    except Exception:
                        pass

                # Fallback: use player's current dimension
                if dimension is None:
                    dimension = player.dimension

            # Create location with dimension as first parameter (add 0.5 to center player on block)
            location = Location(dimension, x + 0.5, y, z + 0.5)
            player.teleport(location)

            # Show success message
            display_dim = self.dimension_names.get(proper_dimension_id, proper_dimension_id)
            if player_dim_normalized == proper_dimension_id:
                player.send_message(f"{ColorFormat.GREEN}Teleported to {display_dim}!")
            else:
                player.send_message(f"{ColorFormat.GREEN}Teleported to coordinates ({x}, {y}, {z})!")

        except Exception as e:
            self.logger.error(f"Teleport failed: {e}")
            player.send_message(f"{ColorFormat.RED}Teleport failed! The location may be invalid or unsafe.")