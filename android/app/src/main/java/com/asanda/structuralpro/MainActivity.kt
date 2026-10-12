package com.asanda.structuralpro
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity: ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  setContent { StructuralProHome() }
 }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StructuralProHome() {
 var screen by remember { mutableStateOf("داشبورد") }
 var projectName by remember { mutableStateOf("پروژه آفلاین") }
 MaterialTheme {
  Scaffold(topBar={TopAppBar(title={Text("StructuralPro")})}) { pad ->
   Column(Modifier.fillMaxSize().padding(pad).padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
    Text("Offline-first • متره و گزارش",style=MaterialTheme.typography.titleMedium)
    Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
     Button(onClick={screen="پروژه‌ها"}) { Text("پروژه‌ها") }
     Button(onClick={screen="متره"}) { Text("متره") }
     Button(onClick={screen="گزارش"}) { Text("گزارش") }
    }
    OutlinedTextField(value=projectName,onValueChange={projectName=it},label={Text("نام پروژه")})
    Text(if(screen=="متره") "ورود متره و ثبت محلی؛ همگام‌سازی بدون حذف تغییرات." else if(screen=="گزارش") "پیش‌نمایش گزارش از داده محلی پروژه." else "پروژه فعال: $projectName")
    AssistChip(onClick={screen="تنظیمات"},label={Text("آفلاین فعال")})
   }
  }
 }
}
