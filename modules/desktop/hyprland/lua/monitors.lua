-- Monitors

-- Fallback rule: any unspecified monitor, preferred mode, auto position, scale 1
hl.monitor({
	output   = "",
	mode     = "preferred",
	position = "auto",
	scale    = "1",
})

-- Internal laptop display
hl.monitor({
	output   = "eDP-1",
	mode     = "1920x1080@60",
	position = "auto",
	scale    = "1",
})

-- Main external HDMI monitor with 10‑bit color
hl.monitor({
	output   = "HDMI-A-1",
	mode     = "2560x1440@144",
	position = "auto",
	scale    = "1.33",
	bitdepth = 10,
})


-- Workspace rules

-- Binds workspaces to monitors (like old `workspace =` lines)

hl.workspace_rule({
	workspace = "1",
	persistent = true,
	monitor = "eDP-1",
	default = true,
})

hl.workspace_rule({
	workspace = "2",
	persistent = true,
	monitor = "eDP-1",
})

hl.workspace_rule({
	workspace = "3",
	persistent = true,
	monitor = "eDP-1",
})

hl.workspace_rule({
	workspace = "4",
	persistent = true,
	monitor = "HDMI-A-1",
	default = true,
})

hl.workspace_rule({
	workspace = "5",
	persistent = true,
	monitor = "HDMI-A-1",
})

hl.workspace_rule({
	workspace = "6",
	persistent = true,
	monitor = "HDMI-A-1",
})

hl.workspace_rule({
	workspace = "7",
	persistent = true,
})

hl.workspace_rule({
	workspace = "8",
	persistent = true,
})

hl.workspace_rule({
	workspace = "9",
	persistent = true,
})

hl.workspace_rule({
	workspace = "10",
	persistent = true,
})
