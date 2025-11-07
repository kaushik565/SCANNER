# SCANNER Display Comparison - Pi vs Windows Test

## Current Pi Display Layout (800x1024)
```
┌─────────────────────────────────────────────────────────────────┐
│ dd/mm/yy          HH:MM                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CARTRIDGE:          [SCAN CARTRIDGE - RED TEXT]                │
│                                                                  │
│  [SETTINGS]                                                      │
│  [KEYBOARD]         MATRIX:     [SCAN MATRIX PACK - RED TEXT]   │
│  [SCAN]                                                          │
│                                                                  │
│                      Acc: 0000        Rej: 0000                 │
│                                                      [LOGOUT]    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  WORKSTATION DETAILS                                     │   │
│  │                                                           │   │
│  │  Line: A      Cubicle: 1      User: operator            │   │
│  │  Jig ID: hostname     IP: 192.168.x.x                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  [rest of screen - black background]                            │
└─────────────────────────────────────────────────────────────────┘
```

### Current Pi Display Features:
✅ Black background with white/red text
✅ Date and time at top
✅ Two main display areas:
   - CARTRIDGE field (shows scanned QR or status)
   - MATRIX field (shows current matrix/mould)
✅ Accept/Reject counters (Acc: / Rej:)
✅ Workstation details box (Line, Cube, User, IP)
✅ Buttons: SETTINGS, KEYBOARD, SCAN, LOGOUT
❌ NO batch information displayed
❌ NO mould range information
❌ NO duplicate count
❌ NO visual feedback for PASS/REJECT status

---

## Windows Test Display Layout (1000x700)
```
┌──────────────────────────────────────────────────────────────────────────┐
│  SCANNER TEST (Blue header)                                              │
├──────────────────────────────────────────────────────────────────────────┤
│  LEFT PANEL:                  │  RIGHT PANEL:                            │
│  ┌─────────────────────────┐  │  ┌──────────────────────────────────┐  │
│  │ Current Configuration   │  │  │ Scan History                     │  │
│  │                          │  │  │                                   │  │
│  │ Line: A                 │  │  │ Time  | QR Code    | Status | Mld│  │
│  │ Cube: 1                 │  │  │ ─────────────────────────────────│  │
│  │ Batch: MVXYZ12345       │  │  │ 10:23 | MAAA0000.. | PASS   | AAA│  │
│  │ User: username          │  │  │ 10:23 | MBBB0000.. | PASS   | BBB│  │
│  │ Moulds: 2 configured    │  │  │ 10:24 | MAAA0000.. | DUPLIC | AAA│  │
│  │ Scanned in batch: 5     │  │  │ ...                               │  │
│  └─────────────────────────┘  │  │                                   │  │
│                                │  │ [Clear History]                   │  │
│  ┌─────────────────────────┐  │  └──────────────────────────────────┘  │
│  │ Scan Counters           │  │                                          │
│  │ ✓ Accepted: 10 (green)  │  │                                          │
│  │ ✗ Rejected: 3  (red)    │  │                                          │
│  └─────────────────────────┘  │                                          │
│                                │                                          │
│  ┌─────────────────────────┐  │                                          │
│  │ QR Code Scanner         │  │                                          │
│  │ [Input field...       ] │  │                                          │
│  │                          │  │                                          │
│  │ Last Scan: PASS (green) │  │                                          │
│  └─────────────────────────┘  │                                          │
│                                │                                          │
│  [⚙ Settings]                 │                                          │
│  [Reset Counters]             │                                          │
└──────────────────────────────────────────────────────────────────────────┘
│ Ready | 10:25:30 PM                                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

### Windows Test Display Features:
✅ Shows batch number prominently
✅ Shows number of moulds configured
✅ Shows duplicate count for current batch
✅ Visual feedback (green/red/orange) for scan status
✅ Scan history table
✅ Accept/Reject counters
✅ Settings with Batch Setup
✅ Status bar with clock

---

## Key Differences to Show User:

### MISSING on Current Pi Display:
1. **No Batch Number** - User doesn't know which batch is active
2. **No Mould Information** - Can't see configured moulds
3. **No Duplicate Count** - Can't see how many scanned in batch
4. **No Visual Status** - Hard to tell PASS vs REJECT quickly
5. **No History** - Can't review recent scans

### What Should Be Added to Pi Display:

#### Option 1: MINIMAL CHANGES (Keep existing layout)
- Add batch number near Line/Cube info:
  ```
  Line: A    Cubicle: 1    Batch: MVXYZ12345
  ```
- Show active mould in MATRIX field when scanning
- Change CARTRIDGE field color:
  - Green background = PASS
  - Red background = REJECT/INVALID
  - Orange background = DUPLICATE

#### Option 2: ENHANCED DISPLAY (Closer to Windows test)
- Add info panel showing:
  ```
  ┌───────────────────────────────────────┐
  │ BATCH INFO                            │
  │ Batch: MVXYZ12345                     │
  │ Moulds: AAA, BBB (2 configured)       │
  │ Scanned: 45                           │
  └───────────────────────────────────────┘
  ```
- Color-coded status in CARTRIDGE field
- Maybe add small history (last 5 scans)

---

## Questions for You:

1. **Do you want to keep the existing Pi layout** and just add:
   - Batch number display
   - Color feedback (green/red/orange)
   - Mould info

2. **Or do you want a bigger redesign** similar to Windows test:
   - Two-panel layout
   - History table
   - More detailed status

3. **What's most important to show?**
   - Batch number? ✓
   - Mould ranges? ✓
   - Duplicate count? ✓
   - Scan history?
   - Visual color feedback? ✓

**Please tell me which option you prefer, or describe what you want to see on the Pi display!**
