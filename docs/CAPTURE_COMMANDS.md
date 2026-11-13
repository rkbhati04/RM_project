# Capture commands

Aman (Jio):

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\preflight.ps1 -Network jio -Interface "Wi-Fi" -NoLive
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run_network.ps1 -Network jio -Interface "Wi-Fi" -MachineLabel "jio"
```

Kunal (Campus):

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\preflight.ps1 -Network campus -Interface "Wi-Fi" -NoLive
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run_network.ps1 -Network campus -Interface "Wi-Fi" -MachineLabel "campus"
```

Defaults are three resolvers, two protocols, 50 Global plus 50 India domains,
and 10 repeats: 6,000 planned captures with shuffled order, resume, and retry
support. Nothing else runs on the capture laptop.
