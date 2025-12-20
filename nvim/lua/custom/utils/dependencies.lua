local M = {}

-- Check if a command is available
local function has_command(cmd)
  return vim.fn.executable(cmd) == 1
end

-- Install command based on package manager
local function install_command(cmd)
  local package_managers = {
    { check = "apt-get", install = "apt-get install -y" },
    { check = "dnf", install = "dnf install -y" },
    { check = "yum", install = "yum install -y" },
    { check = "pacman", install = "pacman -S --noconfirm" },
    { check = "brew", install = "brew install" },
  }

  -- Find available package manager
  local pkg_manager
  for _, pm in ipairs(package_managers) do
    if has_command(pm.check) then
      pkg_manager = pm
      break
    end
  end

  if not pkg_manager then
    print("No supported package manager found")
    return false
  end

  -- Map command to package name
  local pkg_map = {
    fd = {
      apt = "fd-find",
      dnf = "fd-find",
      yum = "fd-find",
      pacman = "fd",
      brew = "fd",
    },
    rg = {
      apt = "ripgrep",
      dnf = "ripgrep",
      yum = "ripgrep",
      pacman = "ripgrep",
      brew = "ripgrep",
    },
  }

  -- Get package name for the command
  local pkg_name = pkg_map[cmd] and pkg_map[cmd][pkg_manager.check] or cmd

  -- Try to install the package
  local install_cmd = pkg_manager.install .. " " .. pkg_name
  local success = os.execute(install_cmd)

  if success then
    print(string.format("Successfully installed %s", cmd))
    -- Special handling for fd-find on Debian/Ubuntu
    if cmd == "fd" and pkg_manager.check == "apt-get" then
      -- Create symlink for fd-find to fd if it doesn't exist
      if not has_command("fd") then
        os.execute("ln -s $(which fdfind) ~/.local/bin/fd")
        -- Add ~/.local/bin to PATH if not already there
        if not string.find(os.getenv("PATH") or "", "/.local/bin") then
          os.execute("mkdir -p ~/.local/bin")
          os.execute('echo "export PATH=\\$PATH:\\$HOME/.local/bin" >> ~/.bashrc')
          print("Added ~/.local/bin to PATH. Please restart your shell or source ~/.bashrc")
        end
      end
    end
    return true
  else
    print(string.format("Failed to install %s", cmd))
    return false
  end
end

-- Check for required dependencies and try to install them if missing
function M.ensure_dependencies()
  local required = {
    { 
      cmd = "fd",
      message = "Required for telescope-repo.nvim and better file finding",
      fallback = function()
        -- Configure telescope-repo to use find instead
        local telescope_ok, telescope = pcall(require, 'telescope')
        if telescope_ok and telescope.extensions and telescope.extensions.repo then
          telescope.extensions.repo.list = {
            command = function()
              return {"find", ".", "-type", "d", "-name", ".git", "-exec", "dirname", "{}", ";"}
            end
          }
          print("Configured telescope-repo to use 'find' command as fallback")
        end
      end
    },
    { 
      cmd = "rg",
      message = "Required for better grep functionality",
      fallback = function()
        -- Could configure to use grep as fallback if needed
        print("Note: Using default vim grep, search performance may be reduced")
      end
    },
  }

  for _, dep in ipairs(required) do
    if not has_command(dep.cmd) then
      print(string.format("Missing dependency: %s (%s)", dep.cmd, dep.message))
      local success = install_command(dep.cmd)
      if not success then
        print(string.format("Please install %s manually", dep.cmd))
        if dep.fallback then
          dep.fallback()
        end
      end
    end
  end
end

return M 