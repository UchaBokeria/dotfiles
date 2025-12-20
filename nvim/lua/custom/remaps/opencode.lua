---@diagnostic disable: different-requires
local map = vim.keymap.set
local is_vscode = vim.g.vscode == 1

-- Only load opencode mappings when not in VSCode
if not is_vscode then
  -- OpenCode state tracking
  local opencode_state = {
    buf = nil,
    win = nil,
    prev_win = nil,
    is_open = false
  }

  -- Function to get current line content
  local function get_current_line()
    return vim.api.nvim_get_current_line()
  end

  -- Function to get visual selection
  local function get_visual_selection()
    local start_pos = vim.fn.getpos("'<")
    local end_pos = vim.fn.getpos("'>")
    local lines = vim.fn.getline(start_pos[2], end_pos[2])
    
    if #lines == 1 then
      return string.sub(lines[1], start_pos[3], end_pos[3])
    else
      lines[1] = string.sub(lines[1], start_pos[3])
      lines[#lines] = string.sub(lines[#lines], 1, end_pos[3])
      return table.concat(lines, '\n')
    end
  end

  -- Function to run opencode command in terminal
  local function run_opencode(cmd)
    -- Save current window
    opencode_state.prev_win = vim.api.nvim_get_current_win()
    
    -- Open terminal window if not open
    if not opencode_state.is_open or not opencode_state.win or not vim.api.nvim_win_is_valid(opencode_state.win) then
      -- Create a new terminal buffer first
      local buf = vim.api.nvim_create_buf(false, true)

      -- Split vertically on the right and open terminal
      vim.cmd('botright vsplit')
      opencode_state.win = vim.api.nvim_get_current_win()
      vim.api.nvim_win_set_width(opencode_state.win, math.floor(vim.o.columns * 0.4))
      opencode_state.is_open = true

      -- Set the buffer in the window
      vim.api.nvim_win_set_buf(opencode_state.win, buf)

      -- Start terminal with opencode command
      vim.fn.termopen(cmd, {
        on_exit = function()
          opencode_state.is_open = false
        end
      })

      -- Store the buffer reference
      opencode_state.buf = buf
    else
      -- Focus existing window
      vim.api.nvim_set_current_win(opencode_state.win)

      -- Send command to existing terminal
      local job_id = vim.b[opencode_state.buf].terminal_job_id
      if job_id then
        vim.fn.chansend(job_id, cmd .. '\n')
      else
        -- Fallback: restart terminal if job_id is not available
        vim.fn.termopen(cmd, {
          on_exit = function()
            opencode_state.is_open = false
          end
        })
      end
    end
    
    -- Enter insert mode
    vim.cmd('startinsert')
  end

  -- Function to toggle opencode terminal
  local function toggle_opencode()
    if opencode_state.is_open and opencode_state.win and vim.api.nvim_win_is_valid(opencode_state.win) then
      -- Close opencode window
      vim.api.nvim_win_close(opencode_state.win, true)
      opencode_state.is_open = false
      
      -- Return to previous window if valid
      if opencode_state.prev_win and vim.api.nvim_win_is_valid(opencode_state.prev_win) then
        vim.api.nvim_set_current_win(opencode_state.prev_win)
      end
    else
      -- Open opencode
      run_opencode('opencode')
    end
  end

  -- Function to go back to previous pane from opencode
  local function opencode_go_back()
    if opencode_state.prev_win and vim.api.nvim_win_is_valid(opencode_state.prev_win) then
      vim.api.nvim_set_current_win(opencode_state.prev_win)
    else
      -- Fallback to previous window
      vim.cmd('wincmd p')
    end
  end



  -- Main OpenCode keymaps (work everywhere)
  map('n', '<leader>o', '', { desc = 'OpenCode' })
  map('n', '<leader>ot', toggle_opencode, { desc = 'OpenCode: Toggle' })

  -- OpenCode ask about current line
  map('n', '<leader>ol', function()
    local line = get_current_line()
    local linenr = vim.fn.line('.')
    local filename = vim.fn.expand('%:t')
    run_opencode(string.format('opencode ask "Explain line %d in %s: %s"', linenr, filename, line))
  end, { desc = 'OpenCode: Ask about line' })

  -- OpenCode ask about selection
  map('v', '<leader>os', function()
    local selection = get_visual_selection()
    local filename = vim.fn.expand('%:t')
    run_opencode(string.format('opencode ask "Explain this code from %s: %s"', filename, selection))
  end, { desc = 'OpenCode: Ask about selection' })

  -- OpenCode ask about current file
  map('n', '<leader>of', function()
    local filename = vim.fn.expand('%:p')
    run_opencode(string.format('opencode ask "Review this file: %s"', filename))
  end, { desc = 'OpenCode: Ask about file' })

  -- OpenCode custom query
  map('n', '<leader>oq', function()
    local query = vim.fn.input('OpenCode query: ')
    if query and query ~= '' then
      run_opencode(string.format('opencode ask "%s"', query))
    end
  end, { desc = 'OpenCode: Custom query' })

  -- Terminal mode keymaps for opencode (only when in terminal)
  vim.api.nvim_create_autocmd('TermEnter', {
    pattern = '*',
    callback = function()
      -- Check if we're in the opencode terminal
      local current_buf = vim.api.nvim_get_current_buf()
      if current_buf == opencode_state.buf then
        -- Set leader keymaps for opencode terminal
        local opts = { buffer = current_buf, silent = true }
        
        -- Navigation back to previous pane (Ctrl + Space)
        map('t', '<C-Space>', function()
          -- Exit terminal mode and go back
          vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<C-\\><C-n>', true, false, true), 'n', false)
          vim.schedule(opencode_go_back)
        end, vim.tbl_extend('force', opts, { desc = 'OpenCode: Go back to previous pane' }))

        -- Note: Use regular space key to insert spaces in terminal mode

        -- Quick toggle (exit and close)
        map('t', '<leader>ot', function()
          vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<C-\\><C-n>', true, false, true), 'n', false)
          vim.schedule(toggle_opencode)
        end, vim.tbl_extend('force', opts, { desc = 'OpenCode: Toggle' }))

        -- New session
        map('t', '<leader>on', function()
          vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<C-\\><C-n>', true, false, true), 'n', false)
          vim.schedule(function()
            run_opencode('opencode')
          end)
        end, vim.tbl_extend('force', opts, { desc = 'OpenCode: New session' }))

        -- Show help
        map('t', '<leader>oh', function()
          vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes('<C-\\><C-n>', true, false, true), 'n', false)
          vim.schedule(function()
            print("OpenCode Terminal Keymaps:")
            print("  <C-Space>        - Go back to previous pane")
            print("  <Space>          - Insert space character")
            print("  <leader>ot       - Toggle opencode")
            print("  <leader>on       - New session")
            print("  <leader>oh       - Show this help")
          end)
        end, vim.tbl_extend('force', opts, { desc = 'OpenCode: Show help' }))
      end
    end,
  })

  -- Normal mode keymaps when in opencode terminal buffer
  vim.api.nvim_create_autocmd('BufEnter', {
    pattern = '*',
    callback = function()
      local current_buf = vim.api.nvim_get_current_buf()
      if current_buf == opencode_state.buf and vim.bo[current_buf].buftype == 'terminal' then
        local opts = { buffer = current_buf, silent = true }
        
        -- Navigation back to previous pane (normal mode)
        map('n', '<C-Space>', opencode_go_back, vim.tbl_extend('force', opts, { desc = 'OpenCode: Go back to previous pane' }))
        map('n', '<leader>ot', toggle_opencode, vim.tbl_extend('force', opts, { desc = 'OpenCode: Toggle' }))
      end
    end,
  })
end