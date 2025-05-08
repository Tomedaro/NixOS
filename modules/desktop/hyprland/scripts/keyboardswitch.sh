#!/usr/bin/env sh

# --- Log file for debugging ---
LOG_FILE="/tmp/keyboardswitch_debug.log"
echo "--- Script started at $(date) for target device: '$1' ---" > "$LOG_FILE"
# set -x # Uncomment for verbose command logging to Hyprland's log/journal

echo "Executing user: $(whoami)" >> "$LOG_FILE"
echo "PATH: $PATH" >> "$LOG_FILE"
echo "Script path ($0): $0" >> "$LOG_FILE"
# --- End initial logging ---

targetKbdDeviceName="$1"

if [ -z "$targetKbdDeviceName" ]; then
    echo "Error: No keyboard device name provided to script." >> "$LOG_FILE"
    notify-send -u critical -a "System" -r 91190 -t 3000 "Keyboard Script Error:" "No target device name supplied."
    exit 1
fi

echo "Attempting to switch layout for specific device: '$targetKbdDeviceName'" >> "$LOG_FILE"
hyprctl switchxkblayout "$targetKbdDeviceName" next
switch_status=$? # Capture exit status of hyprctl command
echo "hyprctl switchxkblayout exit status: $switch_status" >> "$LOG_FILE"

if [ $switch_status -ne 0 ]; then
    echo "Error: hyprctl switchxkblayout command failed for '$targetKbdDeviceName'." >> "$LOG_FILE"
    notify-send -u critical -a "System" -r 91190 -t 3000 "Keyboard Script Error:" "Failed to switch layout for '$targetKbdDeviceName'."
    # Optionally, you might still want to try and notify with the current (unchanged) layout
fi

# It's good practice to re-query the layout *after* attempting to change it.
# sleep 0.05 # Small delay, usually not needed but can be a failsafe

echo "Getting new layout for '$targetKbdDeviceName'..." >> "$LOG_FILE"
newLayout=$(hyprctl -j devices | jq -r --arg KBD_NAME "$targetKbdDeviceName" '.keyboards[] | select(.name == $KBD_NAME) | .active_keymap')
echo "Queried new layout: '$newLayout'" >> "$LOG_FILE"

if [ -n "$newLayout" ]; then
    prettyKbdName=$(echo "$targetKbdDeviceName" | sed -e 's/-/ /g' -e 's/_/ /g' -e 's/\b\(.\)/\u\1/g')
    notify-send -a "System" -r 91190 -t 1200 -i "$HOME/.config/hypr/icons/keyboard.svg" "${newLayout}"
else
    notify-send -u warning -a "System" -r 91190 -t 3000 "Keyboard Script Error:" "Could not retrieve layout for '$targetKbdDeviceName' (it might have been switched)."
fi

echo "--- Script finished for device: '$1' ---" >> "$LOG_FILE"
