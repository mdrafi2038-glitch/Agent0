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


# Simple Client-only background-process clearer (Android 10+).
# This does not claim to force-stop apps or remove their Recent Tasks.
stopper = app / "src/main/java/com/example/BackgroundClearActivity.kt"
stopper.write_text(r"""package com.example

import android.app.Activity
import android.app.ActivityManager
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.Toast

class BackgroundClearActivity : Activity() {
    private data class AppItem(val packageName: String, val label: String)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Clear Background"
        val launchIntent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val apps = packageManager.queryIntentActivities(launchIntent, 0)
            .map { AppItem(it.activityInfo.packageName, it.loadLabel(packageManager).toString()) }
            .filter { it.packageName != packageName }
            .distinctBy { it.packageName }
            .sortedBy { it.label.lowercase() }

        val prefs = getSharedPreferences("background_clear_prefs", Context.MODE_PRIVATE)
        val savedPackage = prefs.getString("selected_package", "") ?: ""
        val list = ListView(this)
        list.choiceMode = ListView.CHOICE_MODE_SINGLE
        list.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_single_choice, apps.map { it.label + if (it.packageName == savedPackage) "  ✓ Selected" else "" })
        val savedIndex = apps.indexOfFirst { it.packageName == savedPackage }
        if (savedIndex >= 0) list.setItemChecked(savedIndex, true)
        list.setOnItemClickListener { _, _, position, _ ->
            val chosen = apps[position]
            prefs.edit().putString("selected_package", chosen.packageName).putString("selected_label", chosen.label).apply()
            Toast.makeText(this, "Saved selection: " + chosen.label, Toast.LENGTH_SHORT).show()
            list.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_single_choice, apps.map { it.label + if (it.packageName == chosen.packageName) "  ✓ Selected" else "" })
            list.setItemChecked(position, true)
        }
        val clear = android.widget.Button(this).apply {
            text = "Request background clear for selected app"
            setOnClickListener {
                val pkg = prefs.getString("selected_package", "") ?: ""
                val target = apps.firstOrNull { it.packageName == pkg }
                if (target == null) Toast.makeText(this@BackgroundClearActivity, "Select an app first", Toast.LENGTH_SHORT).show()
                else showActions(target)
            }
        }
        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(clear)
            addView(list, android.widget.LinearLayout.LayoutParams(-1, 0, 1f))
        }
        setContentView(layout)
    }

    private fun showActions(app: AppItem) {
        AlertDialog.Builder(this)
            .setTitle(app.label)
            .setItems(arrayOf("Clear Background", "Open App Info")) { _, which ->
                when (which) {
                    0 -> {
                        try {
                            val manager = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
                            manager.killBackgroundProcesses(app.packageName)
                            Toast.makeText(this,
                                "Background-process clear requested. Android may keep some work running.",
                                Toast.LENGTH_LONG).show()
                        } catch (_: Exception) {
                            Toast.makeText(this, "Could not request background clear.", Toast.LENGTH_LONG).show()
                        }
                    }
                    1 -> startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + app.packageName)))
                }
            }
            .show()
    }
}
""")

manifest_text = manifest.read_text()
permission = 'android.permission.KILL_BACKGROUND_PROCESSES'
if permission not in manifest_text:
    manifest_text = manifest_text.replace("<application", '    <uses-permission android:name="android.permission.KILL_BACKGROUND_PROCESSES" />\n    <queries>\n        <intent><action android:name="android.intent.action.MAIN" /><category android:name="android.intent.category.LAUNCHER" /></intent>\n    </queries>\n\n    <application', 1)
# Keep the background-clear helper inside the Client app, never as a separate launcher app.
if 'android:name=".BackgroundClearActivity"' not in manifest_text:
    activity_decl = '''
        <activity
            android:name=".BackgroundClearActivity"
            android:enabled="${clientActivityEnabled}"
            android:exported="false"
            android:label="Clear Background" />
'''
    manifest_text = manifest_text.replace("</application>", activity_decl + "    </application>", 1)
else:
    manifest_text = re.sub(
        r'<activity\s+android:name="\.BackgroundClearActivity".*?</activity>',
        '<activity android:name=".BackgroundClearActivity" android:enabled="${clientActivityEnabled}" android:exported="false" android:label="Clear Background" />',
        manifest_text,
        flags=re.S
    )
manifest.write_text(manifest_text)


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
      applicationId = "com.personalagent.client"
      manifestPlaceholders["clientActivityEnabled"] = "true"
      manifestPlaceholders["adminActivityEnabled"] = "false"
    }
    create("admin") {
      dimension = "appRole"
      applicationId = "com.personalagent.admin"
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
                        text = "No client paired yet. Generate a code here, then enter it on the Client phone and approve the request there.",
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
        val completed = java.util.concurrent.atomic.AtomicBoolean(false)
        fun finish(uid: String?, error: String?) {
            if (completed.compareAndSet(false, true)) done(uid, error)
        }
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            finish(null, "Firebase sign-in timed out. Check internet and Firebase Authentication.")
        }, 15000L)
        try {
            val auth = FirebaseAuth.getInstance()
            val currentUser = auth.currentUser
            if (currentUser != null) { finish(currentUser.uid, null); return }
            auth.signInAnonymously()
                .addOnSuccessListener { finish(it.user?.uid, null) }
                .addOnFailureListener { finish(null, it.message ?: "Firebase sign-in failed") }
        } catch (e: Exception) {
            finish(null, "Firebase configuration missing or unavailable: " + (e.message ?: "check google-services.json and Authentication providers."))
        }
    }

    fun create(context: Context, done: (String?, String?) -> Unit) = signIn { uid, err ->
        if (uid == null) { done(null, err); return@signIn }
        val alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        val secureRandom = java.security.SecureRandom()
        val token = (1..8).map { alphabet[secureRandom.nextInt(alphabet.length)] }.joinToString("")
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

    fun revoke(context: Context, token: String) {
        if (token.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {
            try {
                FirebaseDatabase.getInstance().reference.child(ROOT).child(token).child("revoked")
                    .setValue(true)
            } catch (_: Exception) { }
        }
    }

    fun request(raw: String, done: (String?, String?) -> Unit) {
        val completed = java.util.concurrent.atomic.AtomicBoolean(false)
        fun finish(token: String?, error: String?) {
            if (completed.compareAndSet(false, true)) done(token, error)
        }
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            finish(null, "Pairing request timed out. Check database rules, internet, and Firebase project URL.")
        }, 20000L)
        val token = raw.trim().uppercase()
        if (!token.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {
            finish(null, "Enter the 8-character code from Client."); return
        }
        signIn { uid, err ->
            if (uid == null) { finish(null, err); return@signIn }
            try {
                val ref = FirebaseDatabase.getInstance().reference.child(ROOT).child(token)
                ref.get().addOnSuccessListener { snap ->
                    val created = snap.child("createdAt").getValue(Long::class.java) ?: 0L
                    if (!snap.exists() || snap.child("revoked").getValue(Boolean::class.java) == true ||
                        (snap.child("approved").getValue(Boolean::class.java) != true &&
                         System.currentTimeMillis() - created > EXPIRY)) {
                        finish(null, "Code invalid or expired. Generate a new one on Client."); return@addOnSuccessListener
                    }
                    if (snap.child("approved").getValue(Boolean::class.java) == true) {
                        finish(null, "This code has already been used."); return@addOnSuccessListener
                    }
                    ref.child("adminUid").setValue(uid).addOnSuccessListener {
                        ref.child("adminRequestedAt").setValue(System.currentTimeMillis())
                            .addOnSuccessListener { finish(token, null) }
                            .addOnFailureListener { finish(null, "Could not write adminRequestedAt: " + (it.message ?: "permission denied")) }
                    }.addOnFailureListener { finish(null, "Could not write adminUid: " + (it.message ?: "permission denied")) }
                }.addOnFailureListener { finish(null, "Database read failed: " + (it.message ?: "check Firebase rules")) }
            } catch (e: Exception) { finish(null, e.message ?: "Firebase database unavailable") }
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
        if (!token.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) return null
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
        mutableStateOf(context.getSharedPreferences("agent_pairing", 0).getString(if (isAdmin) "admin_token" else "client_token", "") ?: "")
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
            paired = snap.child("approved").getValue(Boolean::class.java) == true
            if (!snap.exists() || snap.child("revoked").getValue(Boolean::class.java) == true ||
                (!paired && System.currentTimeMillis() - created > 600000L)) {
                status = if (snap.child("revoked").getValue(Boolean::class.java) == true)
                    "Old code replaced. Generate a new code."
                else "Pairing code expired. Generate a new code."
                requested = false
            } else {
                deviceName = snap.child("deviceName").getValue(String::class.java) ?: "Client device"
                requested = snap.child("adminRequestedAt").exists()
                status = if (paired) "Permanently paired (until owner unpairs): " + deviceName
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
                else "Generate a pairing code. After approval, this pairing stays saved until the Client owner replaces it.",
                color = CyberTextSecondary, fontSize = 12.sp
            )
            if (!isAdmin && !paired) {
                Button(onClick = {
                    busy = true; error = ""
                    val oldToken = activeToken
                    if (oldToken.isNotBlank()) PairingRepository.revoke(context, oldToken)
                    PairingRepository.create(context) { token, message ->
                        busy = false
                        if (token != null) {
                            activeToken = token
                            requested = false
                            status = "New code generated. Previous code is invalid. Share this code with Admin."
                        } else error = message ?: "Pairing failed"
                    }
                }, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Creating…" else if (activeToken.isBlank()) "Generate pairing code" else "Generate new code")
                }
            }
            if (isAdmin && !paired) {
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it.filter(Char::isLetterOrDigit).uppercase().take(8) },
                    label = { Text("8-character pairing code") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None),
                    modifier = Modifier.fillMaxWidth()
                )
                Button(onClick = {
                    busy = true; error = ""
                    PairingRepository.request(code) { token, message ->
                        busy = false
                        if (token != null) {
                            activeToken = token
                            context.getSharedPreferences("agent_pairing", 0).edit().putString("admin_token", token).apply()
                            status = "Request sent. Waiting for Client approval."
                        }
                        else error = message ?: "Could not request pairing"
                    }
                }, enabled = !busy && code.length == 8, modifier = Modifier.fillMaxWidth()) {
                    Text(if (busy) "Sending…" else "Request pairing")
                }
            }
            if (!isAdmin && activeToken.isNotBlank()) {
                Text("Code expires in 10 minutes until approved:", color = CyberWarningAmber, fontWeight = FontWeight.Bold)
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
    },
    "commands": {
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
        'if (!snap.exists() || snap.child("revoked").getValue(Boolean::class.java) == true || (!snap.child("approved").getValue(Boolean::class.java).let { it == true } && System.currentTimeMillis() - created > 600000L)) {',
        'if (!snap.exists() || snap.child("revoked").getValue(Boolean::class.java) == true || (snap.child("approved").getValue(Boolean::class.java) != true && System.currentTimeMillis() - created > 600000L)) {'
    )
    old_status = '''                status = if (paired) "Permanently paired (until owner unpairs): " + deviceName
                    else if (requested && !isAdmin) "Admin requests pairing. Review and approve below."
                    else "Waiting for Client owner approval"'''
    new_status = '''                status = if (paired) "Permanently paired (until owner unpairs): " + deviceName
                    else if (requested && !isAdmin) "Admin requests pairing. Review and approve below."
                    else "Waiting for Client owner approval"
                if (paired && isAdmin) {
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
    if old_status in panel_source:
        panel_source = panel_source.replace(old_status, new_status, 1)
    panel_path.write_text(panel_source)

# Ensure Firebase Auth/Realtime Database dependencies are present even if the ZIP's
# version-catalog aliases differ from the names expected by an earlier script revision.
g = gradle.read_text()
if 'implementation("com.google.firebase:firebase-auth")' not in g or 'implementation("com.google.firebase:firebase-database")' not in g:
    dep_match = re.search(r'(?m)^\s*dependencies\s*\{', g)
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


# Ensure the Google Services plugin and Firebase configuration are present in the
# generated flavor build. The Firebase app IDs below belong to private-agent-98752.
root_gradle_kts = root / "build.gradle.kts"
root_gradle_groovy = root / "build.gradle"
module_gradle = gradle
root_gradle = root_gradle_kts if root_gradle_kts.exists() else root_gradle_groovy
if not root_gradle.exists():
    raise SystemExit("Could not find root Gradle build file for Google Services plugin")
root_text = root_gradle.read_text()
if not re.search(r"google[.-]?services", root_text, re.I):
    plugin_line = '    id("com.google.gms.google-services") version "4.4.2" apply false\n' if root_gradle.suffix == ".kts" else "    id 'com.google.gms.google-services' version '4.4.2' apply false\n"
    close = root_text.find("}")
    if close < 0:
        raise SystemExit("Could not find root plugins block")
    root_text = root_text[:close] + plugin_line + root_text[close:]
    root_gradle.write_text(root_text)

module_text = module_gradle.read_text()
if not re.search(r"google[.-]?services", module_text, re.I):
    plugin_marker = 'plugins {'
    pos = module_text.find(plugin_marker)
    if pos < 0:
        raise SystemExit("Could not find app module plugins block")
    close = module_text.find("}", pos)
    if close < 0:
        raise SystemExit("Could not find end of app module plugins block")
    plugin_line = '    id("com.google.gms.google-services")\n' if module_gradle.suffix == ".kts" else "    id 'com.google.gms.google-services'\n"
    module_text = module_text[:close] + plugin_line + module_text[close:]
    module_gradle.write_text(module_text)

firebase_config = {
    "project_info": {
        "project_number": "231949189294",
        "project_id": "private-agent-98752",
        "storage_bucket": "private-agent-98752.firebasestorage.app",
        "firebase_url": "https://private-agent-98752-default-rtdb.firebaseio.com"
    },
    "client": [
        {
            "client_info": {
                "mobilesdk_app_id": "1:231949189294:android:c0441a03498fa1ed962d3f",
                "android_client_info": {"package_name": "com.personalagent.client"}
            },
            "api_key": [{"current_key": "AIzaSyBALuDDvkUNtO68bW1dX4mXPzy4AR5DIGg"}],
            "services": {"appinvite_service": {"other_platform_oauth_client": []}}
        },
        {
            "client_info": {
                "mobilesdk_app_id": "1:231949189294:android:a672a0901da1a415962d3f",
                "android_client_info": {"package_name": "com.personalagent.admin"}
            },
            "api_key": [{"current_key": "AIzaSyBALuDDvkUNtO68bW1dX4mXPzy4AR5DIGg"}],
            "services": {"appinvite_service": {"other_platform_oauth_client": []}}
        }
    ],
    "configuration_version": "1"
}
import json
(app / "google-services.json").write_text(json.dumps(firebase_config, indent=2) + "\n")

for path in (main, admin):
    content = path.read_text()
    for marker in ("open_admin_app_btn", "open_client_app_btn", "Switch to Admin App Button", "Switch to Client App"):
        if marker in content:
            raise SystemExit(f"Cross-app switch control still present: {marker} in {path}")
print(f"Customized split Client/Admin flavors in {root}")


# Persistent paired-client command delivery. Commands are queued in Firebase and
# received by the Client foreground service. Only non-destructive, owner-approved
# actions are remotely executable; power-off/wipe/camera capture are intentionally excluded.
service_path = app / "src/main/java/com/example/service/AgentService.kt"
if service_path.exists():
    service = service_path.read_text()
    imports = [
        "import com.google.firebase.database.DataSnapshot",
        "import com.google.firebase.database.DatabaseError",
        "import com.google.firebase.database.DatabaseReference",
        "import com.google.firebase.database.FirebaseDatabase",
        "import com.google.firebase.database.ChildEventListener",
        "import com.example.manager.AgentCommandHandler"
    ]
    for imp in imports:
        if imp not in service:
            service = service.replace("import com.example.manager.SecurityRepository\n", "import com.example.manager.SecurityRepository\n" + imp + "\n", 1)
    if "private var remoteCommandRef: DatabaseReference? = null" not in service:
        service = service.replace(
            "    private var accelerometer: Sensor? = null\n",
            "    private var accelerometer: Sensor? = null\n    private var remoteCommandRef: DatabaseReference? = null\n    private var remoteCommandListener: ChildEventListener? = null\n",
            1
        )
    if "attachRemoteCommandQueue()" not in service:
        service = service.replace(
            "        registerMotionSensor()\n",
            "        registerMotionSensor()\n        attachRemoteCommandQueue()\n",
            1
        )
        service = service.replace(
            "    private fun registerMotionSensor() {",
            """    private fun attachRemoteCommandQueue() {
        val token = getSharedPreferences("agent_pairing", Context.MODE_PRIVATE)
            .getString("client_token", null)?.takeIf { it.matches(Regex("^[A-HJ-NP-Z2-9]{8}$")) } ?: return
        try {
            val ref = FirebaseDatabase.getInstance().reference.child("commands").child(token)
            remoteCommandRef = ref
            val listener = object : ChildEventListener {
                override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                    val status = snapshot.child("status").getValue(String::class.java) ?: "PENDING"
                    if (status != "PENDING") return
                    val id = snapshot.child("id").getValue(String::class.java) ?: snapshot.key ?: return
                    val typeName = snapshot.child("type").getValue(String::class.java) ?: return
                    val allowed = setOf("TRIGGER_SIREN", "STOP_SIREN", "REQUEST_DIAGNOSTICS", "LOCK_DEVICE")
                    if (typeName !in allowed) {
                        ref.child(id).child("status").setValue("REJECTED_UNSUPPORTED")
                        return
                    }
                    ref.child(id).child("status").setValue("RUNNING")
                    try {
                        val type = com.example.model.CommandType.valueOf(typeName)
                        val command = com.example.model.AdminCommand(
                            id = id,
                            type = type,
                            targetDeviceId = token,
                            issuedAt = snapshot.child("issuedAt").getValue(Long::class.java) ?: System.currentTimeMillis()
                        )
                        AgentCommandHandler(this@AgentService).executeCommandSync(command)
                        ref.child(id).updateChildren(mapOf(
                            "status" to "EXECUTED",
                            "resultSummary" to "Client handled command",
                            "completedAt" to System.currentTimeMillis()
                        ))
                    } catch (e: Exception) {
                        ref.child(id).updateChildren(mapOf(
                            "status" to "FAILED",
                            "resultSummary" to (e.localizedMessage ?: "Execution failed"),
                            "completedAt" to System.currentTimeMillis()
                        ))
                    }
                }
                override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {}
                override fun onChildRemoved(snapshot: DataSnapshot) {}
                override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {}
                override fun onCancelled(error: DatabaseError) {
                    SecurityRepository.logEvent("Remote command listener unavailable", error.message,
                        com.example.model.EventSeverity.WARNING, com.example.model.EventType.REMOTE_COMMAND)
                }
            }
            remoteCommandListener = listener
            ref.addChildEventListener(listener)
        } catch (e: Exception) {
            SecurityRepository.logEvent("Remote command setup failed", e.localizedMessage ?: "Firebase unavailable",
                com.example.model.EventSeverity.WARNING, com.example.model.EventType.REMOTE_COMMAND)
        }
    }

    private fun registerMotionSensor() {""",
            1
        )
    if "remoteCommandRef?.let" not in service:
        service = service.replace(
            "        sensorManager?.unregisterListener(this)\n",
            "        sensorManager?.unregisterListener(this)\n        remoteCommandRef?.let { ref -> remoteCommandListener?.let { ref.removeEventListener(it) } }\n",
            1
        )
    service_path.write_text(service)

security_path = app / "src/main/java/com/example/manager/SecurityRepository.kt"
if security_path.exists():
    sec = security_path.read_text()
    if "FirebaseDatabase.getInstance().reference.child(\"commands\")" not in sec:
        sec = sec.replace(
            "    fun addCommand(command: AdminCommand) {\n        _commands.update { current ->",
            """    fun addCommand(command: AdminCommand) {
        // Remote queue is addressed by the approved pairing token. Unsupported
        // remote command types are rejected by the Client service.
        if (command.targetDeviceId.matches(Regex("^[A-HJ-NP-Z2-9]{8}$"))) {
            try {
                com.google.firebase.database.FirebaseDatabase.getInstance().reference
                    .child("commands").child(command.targetDeviceId).child(command.id)
                    .setValue(mapOf(
                        "id" to command.id,
                        "type" to command.type.name,
                        "targetDeviceId" to command.targetDeviceId,
                        "issuedAt" to command.issuedAt,
                        "status" to "PENDING"
                    ))
                    .addOnSuccessListener {
                        logEvent(
                            "Remote command queued",
                            "Command " + command.type.name + " queued for paired Client token " + command.targetDeviceId.take(8),
                            EventSeverity.INFO,
                            EventType.REMOTE_COMMAND
                        )
                    }
                    .addOnFailureListener { error ->
                        logEvent(
                            "Remote command send failed",
                            error.message ?: "Firebase rejected command write. Check authenticated session and Realtime Database rules.",
                            EventSeverity.WARNING,
                            EventType.REMOTE_COMMAND
                        )
                    }
            } catch (error: Exception) {
                logEvent(
                    "Remote command send failed",
                    error.message ?: "Firebase database unavailable",
                    EventSeverity.WARNING,
                    EventType.REMOTE_COMMAND
                )
            }
        }
        _commands.update { current ->"""
        )
        sec_path.write_text(sec)

panel_path = app / "src/main/java/com/example/ui/components/PairingPanel.kt"
if panel_path.exists():
    panel_source = panel_path.read_text()
    # Keep the Admin's active token across app restarts, just like the Client token.
    panel_source = panel_source.replace(
        'mutableStateOf(if (isAdmin) "" else context.getSharedPreferences("agent_pairing", 0).getString("client_token", "") ?: "")',
        'mutableStateOf(context.getSharedPreferences("agent_pairing", 0).getString(if (isAdmin) "admin_token" else "client_token", "") ?: "")'
    )
    panel_source = panel_source.replace(
        'if (token != null) { activeToken = token; status = "Request sent. Waiting for Client approval." }',
        'if (token != null) { activeToken = token; context.getSharedPreferences("agent_pairing", 0).edit().putString("admin_token", token).apply(); status = "Request sent. Waiting for Client approval." }'
    )
    panel_source = panel_source.replace(
        'if (!snap.exists() || (snap.child("approved").getValue(Boolean::class.java) != true && System.currentTimeMillis() - created > 600000L)) {',
        'if (!snap.exists() || (snap.child("approved").getValue(Boolean::class.java) != true && System.currentTimeMillis() - created > 600000L)) {'
    )
    panel_path.write_text(panel_source)

rules_path = root / "database.rules.json"
rules_path.write_text('''{
  "rules": {
    "pairRequests": {
      "$token": {
        ".read": "auth != null",
        ".write": "auth != null"
      }
    },
    "commands": {
      "$token": {
        ".read": "auth != null",
        ".write": "auth != null"
      }
    }
  }
}
''')


# Email/password Firebase account sign-in so the same account can be used on
# both apps and its Firebase UID survives process restarts/reinstalls.
pair_repo = app / "src/main/java/com/example/manager/PairingRepository.kt"
if pair_repo.exists():
    psrc = pair_repo.read_text()
    if "fun authenticateAccount(" not in psrc:
        method = """
    fun authenticateAccount(email: String, password: String, create: Boolean, done: (String?, String?) -> Unit) {
        val e = email.trim()
        if (e.isBlank() || password.length < 6) {
            done(null, "Enter a valid email and password (at least 6 characters).")
            return
        }
        val completed = java.util.concurrent.atomic.AtomicBoolean(false)
        val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
        fun finish(uid: String?, message: String?) {
            if (completed.compareAndSet(false, true)) {
                mainHandler.removeCallbacksAndMessages(null)
                mainHandler.post { done(uid, message) }
            }
        }
        // Never leave the UI stuck on "Signing in…" if Firebase does not complete its Task.
        mainHandler.postDelayed({
            finish(null, "Sign-in timed out after 20 seconds. Check internet, Firebase Authentication > Email/Password, and the app's google-services.json.")
        }, 20000L)
        try {
            val auth = FirebaseAuth.getInstance()
            val task = if (create) auth.createUserWithEmailAndPassword(e, password)
                       else auth.signInWithEmailAndPassword(e, password)
            task.addOnSuccessListener { finish(it.user?.uid, null) }
                .addOnFailureListener { finish(null, it.message ?: "Firebase account sign-in failed") }
        } catch (e: Exception) {
            finish(null, e.message ?: "Firebase Authentication unavailable. Check Firebase configuration.")
        }
    }

"""
        psrc = psrc[:psrc.rfind("}")] + method + psrc[psrc.rfind("}"):]
        pair_repo.write_text(psrc)

panel_path = app / "src/main/java/com/example/ui/components/PairingPanel.kt"
if panel_path.exists():
    p = panel_path.read_text()
    if "FIREBASE ACCOUNT" not in p:
        p = p.replace(
            "    var busy by remember { mutableStateOf(false) }",
            """    var busy by remember { mutableStateOf(false) }
    var accountEmail by remember { mutableStateOf("") }
    var accountPassword by remember { mutableStateOf("") }
    var createAccount by remember { mutableStateOf(false) }
    var accountStatus by remember { mutableStateOf("") }"""
        )
        marker = '            Text(if (isAdmin) "PAIR A CLIENT" else "DEVICE PAIRING", color = CyberCyanPrimary, fontWeight = FontWeight.Bold)'
        insert = marker + """
            Text("FIREBASE ACCOUNT", color = CyberCyanPrimary, fontWeight = FontWeight.Bold, fontSize = 12.sp)
            OutlinedTextField(
                value = accountEmail,
                onValueChange = { accountEmail = it },
                label = { Text("Email / username") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            OutlinedTextField(
                value = accountPassword,
                onValueChange = { accountPassword = it },
                label = { Text("Password (6+ characters)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { createAccount = false }, modifier = Modifier.weight(1f)) {
                    Text(if (!createAccount) "✓ Login" else "Login")
                }
                OutlinedButton(onClick = { createAccount = true }, modifier = Modifier.weight(1f)) {
                    Text(if (createAccount) "✓ Create" else "Create account")
                }
            }
            Button(onClick = {
                busy = true; accountStatus = ""
                PairingRepository.authenticateAccount(accountEmail, accountPassword, createAccount) { uid, message ->
                    busy = false
                    accountStatus = if (uid != null) "Account connected. UID: " + uid.take(8) else (message ?: "Account login failed")
                }
            }, enabled = !busy && accountEmail.isNotBlank() && accountPassword.length >= 6, modifier = Modifier.fillMaxWidth()) {
                Text(if (busy) "Signing in…" else if (createAccount) "Create Firebase account" else "Login with Firebase account")
            }
            if (accountStatus.isNotBlank()) Text(accountStatus, color = CyberTextSecondary, fontSize = 12.sp)
"""
        p = p.replace(marker, insert, 1)
        panel_path.write_text(p)


# Admin must queue commands for the paired Client instead of executing them on itself.
admin_screen = app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt"
if admin_screen.exists():
    a = admin_screen.read_text()
    if "LaunchedEffect(devices)" not in a:
        if "import androidx.compose.runtime.LaunchedEffect\n" not in a:
            a = a.replace("import androidx.compose.runtime.Composable\n", "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.LaunchedEffect\n", 1)
        a = a.replace(
            '    var selectedDeviceId by remember { mutableStateOf("") }',
            '''    var selectedDeviceId by remember { mutableStateOf("") }
    LaunchedEffect(devices) {
        if (selectedDeviceId.isBlank() && devices.isNotEmpty()) {
            selectedDeviceId = devices.first().deviceId
        }
    }''',
            1
        )
    a = a.replace("    val handler = remember { AgentCommandHandler(context) }\n", "")
    a = a.replace("                            handler.executeCommand(cmd)\n", "")
    a = a.replace("                        handler.executeCommand(cmd)\n", "")
    admin_screen.write_text(a)


# Admin action: clear nonessential background work owned by the Client app.
# Android does not allow an ordinary app to kill every other app's processes.
security_state = app / "src/main/java/com/example/model/SecurityState.kt"
if security_state.exists():
    src = security_state.read_text()
    if "CLEAR_BACKGROUND_PROCESSES" not in src:
        src = src.replace("    POWER_OFF\n}", "    POWER_OFF\n}")
        security_state.write_text(src)

service_path = app / "src/main/java/com/example/service/AgentService.kt"
if service_path.exists():
    src = service_path.read_text()
    if "fun clearNonessentialBackgroundTasks()" not in src:
        src = src.replace(
            "    private var remoteCommandListener: ChildEventListener? = null\n",
            "    private var remoteCommandListener: ChildEventListener? = null\n    private var telemetryJob: Job? = null\n    @Volatile private var backgroundTasksCleared = false\n",
            1
        )
        src = src.replace(
            "        serviceScope.launch {\n            while (isActive) {\n                val tel = telemetryManager.gatherTelemetry()\n                SecurityRepository.updateTelemetry(tel)\n                delay(15000)\n            }\n        }",
            "        telemetryJob = serviceScope.launch {\n            while (isActive && !backgroundTasksCleared) {\n                val tel = telemetryManager.gatherTelemetry()\n                SecurityRepository.updateTelemetry(tel)\n                delay(15000)\n            }\n        }",
            1
        )
        src = src.replace(
            '    private fun attachRemoteCommandQueue() {',
            '''    /**
     * Stops this Client app's nonessential polling and motion-sensor work.
     * The Firebase command listener remains alive so the owner can send a restart
     * or diagnostics command later. Android does not permit this app to kill
     * other apps' processes.
     */
    fun clearNonessentialBackgroundTasks(): String {
        backgroundTasksCleared = true
        telemetryJob?.cancel()
        telemetryJob = null
        sensorManager?.unregisterListener(this)
        return "Stopped this Client app's telemetry polling and motion-sensor monitoring. Other apps were not killed; Android does not allow this app to force-stop them."
    }

    private fun attachRemoteCommandQueue() {''',
            1
        )
        src = src.replace(
            'val allowed = setOf("TRIGGER_SIREN", "STOP_SIREN", "REQUEST_DIAGNOSTICS", "LOCK_DEVICE")',
            'val allowed = setOf("TRIGGER_SIREN", "STOP_SIREN", "REQUEST_DIAGNOSTICS", "LOCK_DEVICE")'
        )
        service_path.write_text(src)

handler_path = app / "src/main/java/com/example/manager/AgentCommandHandler.kt"
if handler_path.exists():
    src = handler_path.read_text()


admin_screen = app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt"
if admin_screen.exists():
    src = admin_screen.read_text()



# Managed restriction screen: block ordinary Back navigation; preserve Android system/emergency controls.
lock_path = app / "src/main/java/com/example/lock/LockActivity.kt"
if lock_path.exists():
    lock_path.write_text(r"""package com.example.lock

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.receiver.AgentDeviceAdminReceiver
import com.example.ui.theme.MyApplicationTheme

class LockActivity : ComponentActivity() {
    // Block ordinary Back navigation while the restriction screen is visible.
    // This is not a substitute for managed-device kiosk policy and does not disable emergency/system controls.
    @Deprecated("Deprecated in Android; retained for compatibility")
    override fun onBackPressed() {
        Toast.makeText(this, "This screen is managed by Personal Agent. Contact your administrator to unlock.", Toast.LENGTH_SHORT).show()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        setContent {
            MyApplicationTheme(darkTheme = true) {
                RestrictionScreen(
                    onRestart = {
                        val dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && dpm.isDeviceOwnerApp(packageName)) {
                            try {
                                dpm.reboot(ComponentName(this, AgentDeviceAdminReceiver::class.java))
                            } catch (_: Exception) {
                                Toast.makeText(this, "Restart is unavailable. Use the phone power menu.", Toast.LENGTH_LONG).show()
                            }
                        } else {
                            Toast.makeText(this, "Restart requires Device Owner setup in this Trial build. Use the phone power menu.", Toast.LENGTH_LONG).show()
                        }
                    },
                    onTurnOff = {
                        Toast.makeText(this, "Android does not let this Trial app power off the phone. Use the phone power menu.", Toast.LENGTH_LONG).show()
                    }
                )
            }
        }
    }
}

@Composable
private fun RestrictionScreen(onRestart: () -> Unit, onTurnOff: () -> Unit) {
    var showTurnOffInfo by remember { mutableStateOf(false) }
    Surface(modifier = Modifier.fillMaxSize(), color = Color(0xEE10131B)) {
        Column(
            modifier = Modifier.fillMaxSize().background(Color(0xEE10131B)).padding(28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "Your device is temporarily restricted",
                color = Color.White,
                fontSize = 23.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(28.dp))
            Button(
                onClick = onRestart,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF2878E5))
            ) {
                Text("Restart", modifier = Modifier.padding(vertical = 5.dp))
            }
            Spacer(modifier = Modifier.height(12.dp))
            OutlinedButton(onClick = { showTurnOffInfo = true }, modifier = Modifier.fillMaxWidth()) {
                Text("Turn off", modifier = Modifier.padding(vertical = 5.dp), color = Color.White)
            }
        }
    }
    if (showTurnOffInfo) {
        AlertDialog(
            onDismissRequest = { showTurnOffInfo = false },
            title = { Text("Turn off device") },
            text = { Text("Use your phone's physical power menu to turn it off. This Trial app cannot shut down Android directly.") },
            confirmButton = {
                TextButton(onClick = { showTurnOffInfo = false }) { Text("OK") }
            }
        )
    }
}
""")

admin_screen = app / "src/main/java/com/example/ui/screens/AdminControllerScreen.kt"
if admin_screen.exists():
    src = admin_screen.read_text()
    token_expr = '(context.getSharedPreferences("agent_pairing", Context.MODE_PRIVATE).getString("admin_token", "") ?: "")'
    src = src.replace("targetDeviceId = selectedDeviceId", "targetDeviceId = " + token_expr)
    src = src.replace('title = "Power Off",\n                        desc = "Remote phone shutdown"', 'title = "Lock + Power Options",\n                        desc = "Show Client restriction screen"')
    src = src.replace('Text("Confirm Remote Power Off", color = CyberAlertCrimson, fontWeight = FontWeight.Bold)', 'Text("Show Client Power Options", color = CyberAlertCrimson, fontWeight = FontWeight.Bold)')
    src = src.replace(
        "This will trigger an immediate system shutdown on the client device.",
        "This will open the Client restriction screen. Actual restart or shutdown depends on Android permissions."
    )
    src = src.replace("val cmd = AdminCommand(type = CommandType.POWER_OFF, targetDeviceId = " + token_expr + ")", "val cmd = AdminCommand(type = CommandType.LOCK_DEVICE, targetDeviceId = " + token_expr + ")")
    src = src.replace('Toast.makeText(context, "Remote Power Off Instruction Dispatched", Toast.LENGTH_LONG).show()', 'Toast.makeText(context, "Client restriction screen command sent", Toast.LENGTH_LONG).show()')
    src = src.replace(
        'val cmd = AdminCommand(type = CommandType.CAPTURE_PHOTO, targetDeviceId = ' + token_expr + ')\n                            SecurityRepository.addCommand(cmd)\n                            Toast.makeText(context, "Snapshot Command Dispatched", Toast.LENGTH_SHORT).show()',
        'Toast.makeText(context, "Remote photo capture is not implemented in the Trial build.", Toast.LENGTH_LONG).show()'
    )
    src = src.replace(
        'val cmd = AdminCommand(type = CommandType.WIPE_DEVICE, targetDeviceId = ' + token_expr + ')\n                        SecurityRepository.addCommand(cmd)\n                        Toast.makeText(context, "Emergency Wipe Instruction Dispatched", Toast.LENGTH_LONG).show()',
        'Toast.makeText(context, "Remote wipe is not implemented in the Trial build.", Toast.LENGTH_LONG).show()'
    )
    admin_screen.write_text(src)

service_path = app / "src/main/java/com/example/service/AgentService.kt"
if service_path.exists():
    src = service_path.read_text()
    src = src.replace(
        'setOf("TRIGGER_SIREN", "STOP_SIREN", "REQUEST_DIAGNOSTICS", "LOCK_DEVICE", "CLEAR_BACKGROUND_PROCESSES")',
        'setOf("TRIGGER_SIREN", "STOP_SIREN", "REQUEST_DIAGNOSTICS", "LOCK_DEVICE", "CLEAR_BACKGROUND_PROCESSES")'
    )
    service_path.write_text(src)


# Use the configured Realtime Database instance explicitly. Some google-services.json
# files omit database_url, which makes FirebaseDatabase.getInstance() fail at runtime.
database_url = "https://private-agent-98752-default-rtdb.firebaseio.com/"
for kotlin_file in (app / "src/main/java").rglob("*.kt"):
    kotlin_source = kotlin_file.read_text()
    updated_source = kotlin_source.replace(
        "FirebaseDatabase.getInstance()",
        'FirebaseDatabase.getInstance("' + database_url + '")'
    )
    if updated_source != kotlin_source:
        kotlin_file.write_text(updated_source)


# Add visible foreground-service notification and boot recovery for Client flavor.
boot_receiver = app / "src/main/java/com/example/receiver/AgentBootReceiver.kt"
boot_receiver.parent.mkdir(parents=True, exist_ok=True)
boot_receiver.write_text(r"""package com.example.receiver
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import com.example.service.AgentService

class AgentBootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != Intent.ACTION_BOOT_COMPLETED && action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (context.packageName != "com.personalagent.client") return
        val prefs = context.getSharedPreferences("agent_service_settings", Context.MODE_PRIVATE)
        if (!prefs.getBoolean("auto_start_enabled", true) || !prefs.getBoolean("service_enabled", true)) return
        try {
            val i = Intent(context, AgentService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(i) else context.startService(i)
        } catch (_: Exception) { }
    }
}
""")

manifest_text = manifest.read_text()
for permission in [
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />',
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE" />',
    '    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />',
    '    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',
]:
    if permission.split('"')[1] not in manifest_text:
        manifest_text = manifest_text.replace("<application", permission + "\n    <application", 1)
if 'android:name=".service.AgentService"' not in manifest_text:
    manifest_text = manifest_text.replace("</application>", '''
        <service android:name=".service.AgentService" android:enabled="true" android:exported="false"
            android:stopWithTask="false" android:foregroundServiceType="specialUse">
            <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
                android:value="Owner-enabled visible Personal Agent background service" />
        </service>
    </application>''', 1)
if 'android:name=".receiver.AgentBootReceiver"' not in manifest_text:
    manifest_text = manifest_text.replace("</application>", '''
        <receiver android:name=".receiver.AgentBootReceiver" android:enabled="true" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
            </intent-filter>
        </receiver>
    </application>''', 1)
manifest.write_text(manifest_text)

if service_path.exists():
    service = service_path.read_text()
    for imp in [
        "import android.app.Notification", "import android.app.NotificationChannel",
        "import android.app.NotificationManager", "import android.app.PendingIntent",
        "import android.content.Intent", "import android.os.Build",
        "import androidx.core.app.NotificationCompat", "import com.example.MainActivity",
    ]:
        if imp not in service:
            service = service.replace("import android.app.Service\n", "import android.app.Service\n" + imp + "\n", 1)
    if "private fun ensureAgentForegroundNotification()" not in service:
        match = re.search(r"override\s+fun\s+onCreate\s*\(\s*\)\s*\{", service)
        if match:
            start = match.end()
            sup = re.search(r"super\.onCreate\(\s*\)", service[start:])
            if sup:
                pos = start + sup.end()
                service = service[:pos] + "\n        ensureAgentForegroundNotification()\n" + service[pos:]
        helper = r"""
    private fun ensureAgentForegroundNotification() {
        val id = "personal_agent_service"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getSystemService(NotificationManager::class.java).createNotificationChannel(
                NotificationChannel(id, "Personal Agent service", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val pi = PendingIntent.getActivity(this, 1001, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 23) PendingIntent.FLAG_IMMUTABLE else 0))
        val n = NotificationCompat.Builder(this, id)
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setContentTitle("Personal Agent is active")
            .setContentText("Background service is running. Tap to open the app.")
            .setContentIntent(pi).setOngoing(true).setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_SERVICE).setPriority(NotificationCompat.PRIORITY_LOW).build()
        if (Build.VERSION.SDK_INT >= 34) startForeground(1001, n, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        else startForeground(1001, n)
    }
"""
        pos = service.rfind("}")
        if pos >= 0: service = service[:pos] + helper + "\n" + service[pos:]
    if not re.search(r"override\s+fun\s+onStartCommand\s*\(", service):
        pos = service.rfind("}")
        if pos >= 0:
            service = service[:pos] + """
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureAgentForegroundNotification()
        return START_STICKY
    }
""" + service[pos:]
    service_path.write_text(service)

if main.exists():
    source = main.read_text()
    marker = "// AUTO_START_CLIENT_AGENT_SERVICE"
    if marker not in source:
        for imp in ["import android.content.Context", "import android.content.Intent", "import android.os.Build", "import com.example.service.AgentService"]:
            if imp not in source:
                source = source.replace("import android.os.Bundle\n", "import android.os.Bundle\n" + imp + "\n", 1)
        match = re.search(r"override\s+fun\s+onCreate\s*\(\s*savedInstanceState\s*:\s*Bundle\?\s*\)\s*\{", source)
        if match:
            start = match.end()
            sup = re.search(r"super\.onCreate\(\s*savedInstanceState\s*\)", source[start:])
            if sup:
                pos = start + sup.end()
                startup = """
        // AUTO_START_CLIENT_AGENT_SERVICE
        if (packageName == "com.personalagent.client") {
            val agentPrefs = getSharedPreferences("agent_service_settings", Context.MODE_PRIVATE)
            if (agentPrefs.getBoolean("service_enabled", true)) {
                try {
                    val agentIntent = Intent(this, AgentService::class.java)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(agentIntent)
                    else startService(agentIntent)
                } catch (_: Exception) { }
            }
        }
"""
                source = source[:pos] + startup + source[pos:]
        main.write_text(source)


# MDM foundation: explicit Device Admin opt-in and Device Owner readiness checks.
mdm_receiver = app / "src/main/java/com/example/PersonalAgentAdminReceiver.kt"
mdm_receiver.write_text(r"""package com.example
import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast

class PersonalAgentAdminReceiver : DeviceAdminReceiver() {
    override fun onEnabled(context: Context, intent: Intent) {
        Toast.makeText(context, "Personal Agent device admin enabled", Toast.LENGTH_SHORT).show()
    }
    override fun onDisabled(context: Context, intent: Intent) {
        Toast.makeText(context, "Personal Agent device admin disabled", Toast.LENGTH_SHORT).show()
    }
}
""")

mdm_activity = app / "src/main/java/com/example/MdmSetupActivity.kt"
mdm_activity.write_text(r"""package com.example

import android.app.Activity
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

class MdmSetupActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var dpm: DevicePolicyManager
    private lateinit var admin: ComponentName

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "MDM Setup"
        dpm = getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        admin = ComponentName(this, PersonalAgentAdminReceiver::class.java)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 40, 40, 40)
        }
        status = TextView(this).apply { textSize = 16f }
        layout.addView(status)
        layout.addView(Button(this).apply {
            text = "Enable Device Admin"
            setOnClickListener {
                startActivity(Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).putExtra(
                    DevicePolicyManager.EXTRA_DEVICE_ADMIN, admin
                ).putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                    "Enable Personal Agent device management on this phone. You can revoke it in Android settings."))
            }
        })
        layout.addView(Button(this).apply {
            text = "Clear Background (choose app)"
            setOnClickListener { startActivity(Intent(this@MdmSetupActivity, BackgroundClearActivity::class.java)) }
        })
        layout.addView(Button(this).apply {
            text = "Open Android Settings"
            setOnClickListener { startActivity(Intent(android.provider.Settings.ACTION_SETTINGS)) }
        })
        layout.addView(TextView(this).apply {
            text = "\nDevice Owner setup requires Android enterprise provisioning, usually during initial setup after a factory reset. Enabling Device Admin alone is not Device Owner."
            textSize = 14f
        })
        setContentView(layout)
        updateStatus()
    }

    override fun onResume() {
        super.onResume()
        if (::status.isInitialized) updateStatus()
    }

    private fun updateStatus() {
        val isAdmin = dpm.isAdminActive(admin)
        val isOwner = dpm.isDeviceOwnerApp(packageName)
        status.text = "Personal Agent MDM status\n\nDevice Admin: " +
            (if (isAdmin) "Enabled" else "Not enabled") +
            "\nDevice Owner: " + (if (isOwner) "Active" else "Not provisioned") +
            "\n\nAndroid version: " + android.os.Build.VERSION.RELEASE +
            "\nPackage: " + packageName
    }
}
""")

xml_dir = app / "src/main/res/xml"
xml_dir.mkdir(parents=True, exist_ok=True)
(xml_dir / "device_admin_policies.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<device-admin xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-policies>
        <force-lock />
        <wipe-data />
        <reset-password />
        <limit-password />
        <watch-login />
    </uses-policies>
</device-admin>
""")

manifest_text = manifest.read_text()
if "android.permission.BIND_DEVICE_ADMIN" not in manifest_text:
    receiver = '''
        <receiver
            android:name=".PersonalAgentAdminReceiver"
            android:label="Personal Agent Device Admin"
            android:description="@string/app_name"
            android:permission="android.permission.BIND_DEVICE_ADMIN"
            android:exported="true">
            <meta-data android:name="android.app.device_admin" android:resource="@xml/device_admin_policies" />
            <intent-filter><action android:name="android.app.action.DEVICE_ADMIN_ENABLED" /></intent-filter>
        </receiver>
        <activity
            android:name=".MdmSetupActivity"
            android:enabled="${clientActivityEnabled}"
            android:exported="true"
            android:label="MDM Setup">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
'''
    manifest_text = manifest_text.replace("</application>", receiver + "    </application>", 1)
manifest.write_text(manifest_text)
