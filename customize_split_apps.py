from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
app = root / "app"
main = app / "src/main/java/com/example/MainActivity.kt"
admin = app / "src/main/java/com/example/admin/AdminMainActivity.kt"
manifest = app / "src/main/AndroidManifest.xml"
gradle = app / "build.gradle.kts"

s = main.read_text()
s = s.replace('    CONTROLLER("Admin", Icons.Default.ControlCamera),\n', "")
start = s.find("                    // Switch to Admin App Button")
if start >= 0:
    end = s.find("                    // Quick Siren Button in Top Bar", start)
    if end < 0:
        raise SystemExit("Could not find client top-bar button end marker")
    s = s[:start] + s[end:]
s = s.replace("                MainNavTab.CONTROLLER -> AdminControllerScreen()\n", "")
s = s.replace("import androidx.compose.material.icons.filled.AdminPanelSettings\n", "")
s = s.replace("import androidx.compose.material.icons.filled.ControlCamera\n", "")
s = s.replace("import com.example.ui.screens.AdminControllerScreen\n", "")
main.write_text(s)

s = admin.read_text()
s = s.replace("import android.content.Intent\n", "")
s = s.replace("import androidx.compose.material.icons.filled.PhoneAndroid\n", "")
s = s.replace("import androidx.compose.material3.OutlinedButton\n", "")
s = s.replace("import com.example.MainActivity\n", "")
s = s.replace("""                AdminAppRoot(
                    onOpenClientApp = {
                        val intent = Intent(this, MainActivity::class.java).apply {
                            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        }
                        startActivity(intent)
                    }
                )""", "                AdminAppRoot()")
s = s.replace("fun AdminAppRoot(onOpenClientApp: () -> Unit) {", "fun AdminAppRoot() {")
start = s.find("                    // Switch to Client App")
if start >= 0:
    end = s.find("                    // Emergency Siren toggle", start)
    if end < 0:
        raise SystemExit("Could not find admin top-bar button end marker")
    s = s[:start] + s[end:]
admin.write_text(s)

s = manifest.read_text()
s = s.replace('''            android:name=".MainActivity"
            android:exported="true"''', '''            android:name=".MainActivity"
            android:enabled="${clientActivityEnabled}"
            android:exported="true"''')
s = s.replace('''            android:name=".admin.AdminMainActivity"
            android:exported="true"''', '''            android:name=".admin.AdminMainActivity"
            android:enabled="${adminActivityEnabled}"
            android:exported="true"''')
manifest.write_text(s)

s = gradle.read_text()
if 'flavorDimensions += "appRole"' not in s:
    match = re.search(r'  defaultConfig \{.*?^  \}', s, re.S | re.M)
    if not match:
        raise SystemExit("Could not find app defaultConfig block")
    default_block = re.sub(r'minSdk\s*=\s*\d+', 'minSdk = 29', match.group(0))
    flavors = '''
  
  flavorDimensions += "appRole"
  productFlavors {
    create("client") {
      dimension = "appRole"
      applicationIdSuffix = ".client"
      manifestPlaceholders["clientActivityEnabled"] = "true"
      manifestPlaceholders["adminActivityEnabled"] = "false"
    }
    create("admin") {
      dimension = "appRole"
      applicationIdSuffix = ".admin"
      manifestPlaceholders["clientActivityEnabled"] = "false"
      manifestPlaceholders["adminActivityEnabled"] = "true"
    }
  }
'''
    s = s[:match.start()] + default_block + flavors + s[match.end():]
else:
    # Preserve a minimum supported version of Android 10 even on older ZIP revisions.
    s = re.sub(r'minSdk\s*=\s*\d+', 'minSdk = 29', s, count=1)
gradle.write_text(s)

# Never present hard-coded sample phones as connected remote clients.
security = app / "src/main/java/com/example/manager/SecurityRepository.kt"
if security.exists():
    source = security.read_text()
    start = source.find("        if (_managedDevices.value.isEmpty()) {")
    if start >= 0:
        open_brace = source.find("{", start)
        depth = 0
        end = -1
        for i in range(open_brace, len(source)):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end < 0:
            raise SystemExit("Could not safely locate mock managed-device seed block")
        source = source[:start] + """        // Remote devices must come from a real, consent-based pairing/backend.
        _managedDevices.value = emptyList()""" + source[end:]
        security.write_text(source)

screen = app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt"
if screen.exists():
    source = screen.read_text()
    source = source.replace(
        'var selectedDeviceId by remember { mutableStateOf("agent_primary") }',
        'var selectedDeviceId by remember { mutableStateOf("") }'
    )
    old_list = """            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                devices.forEach { dev ->
                    DeviceSelectorCard(
                        device = dev,
                        isSelected = dev.deviceId == selectedDeviceId,
                        onSelect = { selectedDeviceId = dev.deviceId }
                    )
                }
            }"""
    new_list = """            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (devices.isEmpty()) {
                    Text(
                        text = "No client connected. This build does not yet have a live pairing backend; remote devices will appear only after an explicit pairing flow is implemented.",
                        color = CyberWarningAmber,
                        fontSize = 13.sp
                    )
                } else {
                    devices.forEach { dev ->
                        DeviceSelectorCard(
                            device = dev,
                            isSelected = dev.deviceId == selectedDeviceId,
                            onSelect = { selectedDeviceId = dev.deviceId }
                        )
                    }
                }
            }"""
    if old_list in source:
        source = source.replace(old_list, new_list, 1)
    screen.write_text(source)



# Consent-based Firebase pairing (device identity only; no location/camera/remote commands).
catalog = root / "gradle/libs.versions.toml"
if catalog.exists():
    c = catalog.read_text()
    if "firebase-database =" not in c:
        c = c.replace(
            'firebase-auth = { group = "com.google.firebase", name = "firebase-auth" }\n',
            'firebase-auth = { group = "com.google.firebase", name = "firebase-auth" }\n'
            'firebase-database = { group = "com.google.firebase", name = "firebase-database" }\n')
    catalog.write_text(c)

g = gradle.read_text()
if "implementation(libs.firebase.auth)" not in g:
    g = g.replace("  implementation(libs.firebase.ai)\n",
        "  implementation(libs.firebase.ai)\n  implementation(libs.firebase.auth)\n  implementation(libs.firebase.database)\n")
gradle.write_text(g)

repo = app / "src/main/java/com/example/manager/PairingRepository.kt"
repo.parent.mkdir(parents=True, exist_ok=True)
repo.write_text(r'''package com.example.manager

import android.content.Context
import android.os.Build
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.*
import java.util.UUID

object PairingRepository {
    private const val ROOT = "pairRequests"
    private const val EXPIRY = 600000L

    fun signIn(done: (String?, String?) -> Unit) {
        try {
            val auth = FirebaseAuth.getInstance()
            val currentUser = auth.currentUser
            if (currentUser != null) { done(currentUser.uid, null); return }
            auth.signInAnonymously()
                .addOnSuccessListener { done(it.user?.uid, null) }
                .addOnFailureListener { done(null, it.message ?: "Firebase sign-in failed") }
        } catch (e: Exception) {
            done(null, "Firebase configuration missing: add google-services.json and enable Anonymous sign-in.")
        }
    }

    fun create(context: Context, done: (String?, String?) -> Unit) = signIn { uid, err ->
        if (uid == null) { done(null, err); return@signIn }
        val token = UUID.randomUUID().toString().replace("-", "")
        val data = mapOf(
            "clientUid" to uid,
            "deviceName" to (Build.MANUFACTURER + " " + Build.MODEL).trim(),
            "model" to Build.MODEL,
            "osVersion" to ("Android " + Build.VERSION.RELEASE),
            "createdAt" to System.currentTimeMillis(),
            "approved" to false
        )
        try {
            FirebaseDatabase.getInstance().reference.child(ROOT).child(token).setValue(data)
                .addOnSuccessListener {
                    context.getSharedPreferences("agent_pairing", Context.MODE_PRIVATE)
                        .edit().putString("client_token", token).apply()
                    done(token, null)
                }.addOnFailureListener { done(null, it.message ?: "Database write failed; check Firebase rules") }
        } catch (e: Exception) { done(null, e.message ?: "Firebase database unavailable") }
    }

    fun request(raw: String, done: (String?, String?) -> Unit) {
        val token = raw.trim().lowercase()
        if (!token.matches(Regex("^[a-f0-9]{32}$"))) {
            done(null, "Enter the full 32-character code from Client."); return
        }
        signIn { uid, err ->
            if (uid == null) { done(null, err); return@signIn }
            try {
                val ref = FirebaseDatabase.getInstance().reference.child(ROOT).child(token)
                ref.get().addOnSuccessListener { snap ->
                    val created = snap.child("createdAt").getValue(Long::class.java) ?: 0L
                    if (!snap.exists() || System.currentTimeMillis() - created > EXPIRY) {
                        done(null, "Code invalid or expired. Generate a new one on Client."); return@addOnSuccessListener
                    }
                    if (snap.child("approved").getValue(Boolean::class.java) == true) {
                        done(null, "This code has already been used."); return@addOnSuccessListener
                    }
                    ref.child("adminUid").setValue(uid).addOnSuccessListener {
                        ref.child("adminRequestedAt").setValue(System.currentTimeMillis())
                            .addOnSuccessListener { done(token, null) }
                            .addOnFailureListener { done(null, it.message ?: "Pair request failed") }
                    }.addOnFailureListener { done(null, it.message ?: "Pair request failed") }
                }.addOnFailureListener { done(null, it.message ?: "Database read failed; check rules") }
            } catch (e: Exception) { done(null, e.message ?: "Firebase database unavailable") }
        }
    }

    fun approve(token: String, done: (String?) -> Unit) = signIn { uid, err ->
        if (uid == null) { done(err); return@signIn }
        try {
            FirebaseDatabase.getInstance().reference.child(ROOT).child(token).updateChildren(
                mapOf("approved" to true, "pairedClientUid" to uid, "pairedAt" to System.currentTimeMillis())
            ).addOnSuccessListener { done(null) }
                .addOnFailureListener { done(it.message ?: "Approval failed") }
        } catch (e: Exception) { done(e.message ?: "Firebase database unavailable") }
    }

    fun listen(token: String, changed: (DataSnapshot) -> Unit, failed: (String) -> Unit): ValueEventListener? {
        if (!token.matches(Regex("^[a-f0-9]{32}$"))) return null
        return try {
            val ref = FirebaseDatabase.getInstance().reference.child(ROOT).child(token)
            val listener = object : ValueEventListener {
                override fun onDataChange(snapshot: DataSnapshot) = changed(snapshot)
                override fun onCancelled(error: DatabaseError) = failed(error.message)
            }
            ref.addValueEventListener(listener)
            listener
        } catch (e: Exception) { failed(e.message ?: "Firebase unavailable"); null }
    }

    fun remove(token: String, listener: ValueEventListener?) {
        if (listener != null) try {
            FirebaseDatabase.getInstance().reference.child(ROOT).child(token).removeEventListener(listener)
        } catch (_: Exception) { }
    }
}
''')

panel = app / "src/main/java/com/example/ui/components/PairingPanel.kt"
panel.parent.mkdir(parents=True, exist_ok=True)
panel.write_text(r'''package com.example.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.manager.PairingRepository
import com.example.ui.theme.*
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.ValueEventListener

@Composable
fun PairingPanel(isAdmin: Boolean) {
    val context = LocalContext.current
    var code by remember { mutableStateOf("") }
    var activeToken by remember {
        mutableStateOf(if (isAdmin) "" else context.getSharedPreferences("agent_pairing", 0).getString("client_token", "") ?: "")
    }
    var status by remember { mutableStateOf("Not connected") }
    var error by remember { mutableStateOf("") }
    var requested by remember { mutableStateOf(false) }
    var paired by remember { mutableStateOf(false) }
    var deviceName by remember { mutableStateOf("Client device") }
    var busy by remember { mutableStateOf(false) }

    DisposableEffect(activeToken, isAdmin) {
        var listener: ValueEventListener? = null
        if (activeToken.isNotBlank()) listener = PairingRepository.listen(activeToken, { snap: DataSnapshot ->
            val created = snap.child("createdAt").getValue(Long::class.java) ?: 0L
            if (!snap.exists() || System.currentTimeMillis() - created > 600000L) {
                status = "Pairing code expired. Generate a new code."
                paired = false
            } else {
                deviceName = snap.child("deviceName").getValue(String::class.java) ?: "Client device"
                requested = snap.child("adminRequestedAt").exists()
                paired = snap.child("approved").getValue(Boolean::class.java) == true
                status = if (paired) "Connected and approved: " + deviceName
                    else if (requested && !isAdmin) "Admin requests pairing. Review and approve below."
                    else "Waiting for Client owner approval"
            }
        }, { error = it })
        onDispose { PairingRepository.remove(activeToken, listener) }
    }

    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CyberNavyDark)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (isAdmin) "PAIR A CLIENT" else "DEVICE PAIRING", color = CyberCyanPrimary, fontWeight = FontWeight.Bold)
            Text(
                if (isAdmin) "Enter the one-time code shown by Client. Client owner approval is required."
                else "Generate a one-time code. Only device name/model and Android version are shared.",
                color = CyberTextSecondary, fontSize = 12.sp
            )
            if (!isAdmin && activeToken.isBlank()) {
                Button(onClick = {
                    busy = true; error = ""
                    PairingRepository.create(context) { token, message ->
                        busy = false
                        if (token != null) { activeToken = token; status = "Share the code with Admin, then approve the request." }
                        else error = message ?: "Pairing failed"
                    }
                }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Creating…" else "Generate pairing code")
                }
            }
            if (isAdmin && !paired) {
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it.filter(Char::isLetterOrDigit).lowercase().take(32) },
                    label = { Text("32-character pairing code") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None),
                    modifier = Modifier.fillMaxWidth()
                )
                Button(onClick = {
                    busy = true; error = ""
                    PairingRepository.request(code) { token, message ->
                        busy = false
                        if (token != null) { activeToken = token; status = "Request sent. Waiting for Client approval." }
                        else error = message ?: "Could not request pairing"
                    }
                }, enabled = !busy && code.length == 32, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Sending…" else "Request pairing")
                }
            }
            if (!isAdmin && activeToken.isNotBlank()) {
                Text("One-time code (valid 10 minutes):", color = CyberWarningAmber, fontWeight = FontWeight.Bold)
                Text(activeToken, color = CyberWarningAmber, fontFamily = FontFamily.Monospace, fontSize = 13.sp)
                if (requested && !paired) Button(onClick = {
                    busy = true
                    PairingRepository.approve(activeToken) { message ->
                        busy = false
                        if (message == null) status = "Pairing approved" else error = message
                    }
                }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Approving…" else "Approve this Admin")
                }
            }
            Text(status, color = CyberTextSecondary, fontSize = 12.sp)
            if (error.isNotBlank()) Text(error, color = CyberWarningAmber, fontSize = 12.sp)
            if (paired && isAdmin) Text(
                "Consent-based identity pairing only. Remote commands, GPS and camera data are not sent by this pairing flow.",
                color = CyberTextSecondary, fontSize = 11.sp
            )
        }
    }
}
''')

for screen_path, is_admin in [
    (app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt", True),
    (app / "src/main/java/com/example/ui/screens/AgentDashboardScreen.kt", False),
]:
    if screen_path.exists():
        source = screen_path.read_text()
        imp = "import com.example.ui.components.PairingPanel\n"
        if imp not in source:
            source = source.replace("package com.example.ui.screens\n", "package com.example.ui.screens\n\n" + imp, 1)
        anchor = "    ) {\n"
        lazy_start = source.find("LazyColumn(")
        lazy_body = source.find(anchor, lazy_start)
        if lazy_start >= 0 and lazy_body >= 0 and "PairingPanel(isAdmin" not in source:
            role = "true" if is_admin else "false"
            insert = "    ) {\n        item { PairingPanel(isAdmin = " + role + ") }\n"
            source = source[:lazy_body] + source[lazy_body:].replace(anchor, insert, 1)
        screen_path.write_text(source)

(root / "database.rules.json").write_text('''{
  "rules": {
    "pairRequests": {
      "$token": {
        ".read": "auth != null",
        ".write": "auth != null"
      }
    }
  }
}
''')
(root / "PAIRING_SETUP.md").write_text("""# Consent-based Client/Admin pairing

1. Add the correct Firebase google-services.json to the Android app module.
2. In Firebase Authentication, enable Anonymous sign-in.
3. Create a Realtime Database for this Firebase project.
4. Apply database.rules.json in Realtime Database Rules. Rules require authentication; each request uses a random 128-bit token that must be deliberately shared.
5. On Client, generate a code. Enter it on Admin. The Client owner must press Approve this Admin.
6. Pairing expires after 10 minutes. It exchanges device name/model and Android version only; it does not transmit GPS, camera data or remote commands.

Do not use public read/write rules. Firebase configuration and rules must be deployed before cross-phone pairing works.
""")


# Publish the consented client to the Admin device list; keep only basic identity metadata.
sec_path = app / "src/main/java/com/example/manager/SecurityRepository.kt"
if sec_path.exists():
    sec = sec_path.read_text()
    if "fun setPairedDevice(" not in sec:
        sec = sec.replace(
            "    fun addCommand(command: AdminCommand) {",
            """    fun setPairedDevice(device: ManagedDevice) {
        _managedDevices.value = listOf(device)
    }

    fun addCommand(command: AdminCommand) {"""
        )
        sec_path.write_text(sec)

panel_path = app / "src/main/java/com/example/ui/components/PairingPanel.kt"
if panel_path.exists():
    panel_source = panel_path.read_text()
    if "import com.example.manager.SecurityRepository" not in panel_source:
        panel_source = panel_source.replace(
            "import com.example.manager.PairingRepository\n",
            "import com.example.manager.PairingRepository\n"
            "import com.example.manager.SecurityRepository\n"
            "import com.example.model.ManagedDevice\n"
        )
    panel_source = panel_source.replace(
        'if (!snap.exists() || System.currentTimeMillis() - created > 600000L) {',
        'if (!snap.exists() || (snap.child("approved").getValue(Boolean::class.java) != true && System.currentTimeMillis() - created > 600000L)) {'
    )
    panel_source = panel_source.replace(
        'if (paired && isAdmin) status = "Connected and approved: " + deviceName',
        '''if (paired && isAdmin) {
                    status = "Connected and approved: " + deviceName
                    SecurityRepository.setPairedDevice(
                        ManagedDevice(
                            deviceId = activeToken,
                            deviceName = deviceName,
                            model = snap.child("model").getValue(String::class.java) ?: deviceName,
                            osVersion = snap.child("osVersion").getValue(String::class.java) ?: "Android",
                            batteryPercent = 0,
                            isOnline = true,
                            isProtected = false,
                            lastSeenTimestamp = System.currentTimeMillis()
                        )
                    )
                }'''
    )
    panel_path.write_text(panel_source)

# Ensure Firebase Auth/Realtime Database dependencies are present even if the ZIP's
# version-catalog aliases differ from the names expected by an earlier script revision.
g = gradle.read_text()
if 'com.google.firebase:firebase-auth' not in g:
    dep_match = re.search(r'(?m)^dependencies\\s*\\{', g)
    if not dep_match:
        raise SystemExit("Could not find app dependencies block to add Firebase libraries")
    open_brace = g.find("{", dep_match.start())
    depth = 0
    close_brace = -1
    for i in range(open_brace, len(g)):
        if g[i] == "{":
            depth += 1
        elif g[i] == "}":
            depth -= 1
            if depth == 0:
                close_brace = i
                break
    if close_brace < 0:
        raise SystemExit("Could not safely locate dependencies block end")
    firebase = '''
  implementation(platform("com.google.firebase:firebase-bom:34.3.0"))
  implementation("com.google.firebase:firebase-auth")
  implementation("com.google.firebase:firebase-database")
'''
    g = g[:close_brace] + firebase + g[close_brace:]
    gradle.write_text(g)

for path in (main, admin):
    content = path.read_text()
    for marker in ("open_admin_app_btn", "open_client_app_btn", "Switch to Admin App Button", "Switch to Client App"):
        if marker in content:
            raise SystemExit(f"Cross-app switch control still present: {marker} in {path}")
print(f"Customized split Client/Admin flavors in {root}")
