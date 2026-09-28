-- TI-Nspire CX II/CX II CAS companion.
--
-- Paste this source into a new TI-Nspire "Lua Script" document. The stock
-- TI-Nspire Lua runtime cannot open arbitrary TCP/USB connections, so it
-- provides a calculator UI and displays the handoff for the computer bridge.
--
-- A future Ndless transport can replace copy_request/parse_response without
-- changing the UI.

local request_text = ""
local answer_text = "Ready."
local mode = "question"
local notice = "Type a question, then press Enter."

local function trim(value)
    return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function json_escape(value)
    return value:gsub("\\", "\\\\"):gsub('"', '\\"')
        :gsub("\n", "\\n"):gsub("\r", "\\r")
end

local function copy_request()
    request_text = trim(request_text)
    if request_text == "" then
        notice = "Type a question first."
        return
    end
    local payload = '{"id":"nspire-1","question":"' .. json_escape(request_text) .. '"}'
    answer_text = payload
    notice = "Request ready. Ask it in the Mac browser."
end

local function parse_response(raw)
    local answer = raw:match('"answer"%s*:%s*"(.-)"')
    if not answer then
        local err = raw:match('"error"%s*:%s*"(.-)"')
        answer_text = err and ("Bridge error: " .. err) or "Invalid response JSON."
        return
    end
    answer_text = answer:gsub('\\"', '"'):gsub("\\n", "\n"):gsub("\\r", "\r")
    notice = "Answer received."
end

local function paste_response()
    mode = "response"
    answer_text = ""
    notice = "Type/paste response JSON, then press Enter."
end

local function draw(gc)
    gc:setColorRGB(245, 247, 250)
    gc:fillRect(0, 0, 318, 212)
    gc:setColorRGB(25, 45, 75)
    gc:setFont("sansserif", "b", 14)
    gc:drawString("TI-Nspire AI", 10, 8)
    gc:setFont("sansserif", "r", 9)
    gc:setColorRGB(50, 50, 50)
    gc:drawString(notice, 10, 30)
    gc:setColorRGB(255, 255, 255)
    gc:fillRect(10, 48, 298, 62)
    gc:setColorRGB(50, 50, 50)
    gc:drawString("Question:", 16, 52)
    gc:drawString(request_text, 16, 70)
    gc:setColorRGB(230, 237, 247)
    gc:fillRect(10, 120, 298, 70)
    gc:setColorRGB(35, 35, 35)
    gc:drawString("Answer:", 16, 124)
    gc:drawString(answer_text:sub(1, 66), 16, 143)
    gc:setColorRGB(25, 45, 75)
    gc:drawString("[Enter] menu  [1] request  [2] response", 10, 196)
end

function on.paint(gc)
    draw(gc)
end

function on.charIn(char)
    if mode == "question" then
        request_text = request_text .. char
    elseif mode == "menu" then
        if char == "1" then
            copy_request()
        elseif char == "2" then
            paste_response()
        end
    elseif mode == "response" then
        answer_text = answer_text .. char
    end
    platform.window:invalidate()
end

function on.backspaceKey()
    if mode == "response" then
        answer_text = answer_text:sub(1, -2)
    else
        request_text = request_text:sub(1, -2)
    end
    platform.window:invalidate()
end

function on.enterKey()
    if mode == "response" then
        parse_response(answer_text)
        mode = "question"
    elseif mode == "question" then
        mode = "menu"
        notice = "Press 1 to copy the request or 2 to paste an answer."
    else
        mode = "question"
        notice = "Type a question, then press Enter."
    end
    platform.window:invalidate()
end

function on.escapeKey()
    mode = "question"
    platform.window:invalidate()
end
