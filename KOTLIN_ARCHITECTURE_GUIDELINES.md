# Kotlin Architectural Guidelines

## Project Requirements
- **minSdkVersion**: 21 (Android 5.0)
- **Target**: Android TV compatibility
- **UI Framework**: Jetpack Compose with TV Material3

## 1. Jetpack Compose Imports

Always ensure UI-related classes are imported from correct androidx.compose packages:

### Required Imports for Gradients/Shaders
```kotlin
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.geometry.Offset
```

### Common Import Pattern
```kotlin
// Correct
import androidx.compose.foundation.background
import androidx.compose.ui.graphics.Color

// Avoid ambiguous imports
import android.graphics.Color  // Don't use in Compose
```

## 2. API 21 Compatibility

### ThreadLocal Pattern
**Use this pattern instead of `ThreadLocal.withInitial`:**

```kotlin
// API 21 Compatible
private val myThreadLocal = object : ThreadLocal<Type>() { 
    override fun initialValue(): Type = ... 
}

// NOT API 21 Compatible (requires API 26+)
private val myThreadLocal = ThreadLocal.withInitial { ... }
```

### Example from Project
```kotlin
private val _epgSdf = object : ThreadLocal<SimpleDateFormat>() {
    override fun initialValue(): SimpleDateFormat {
        return SimpleDateFormat("yyyyMMddHHmmss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
    }
}
```

## 3. Dependency Alignment

### Check Existing Imports First
Before adding new imports, review the file to:
- Avoid duplicate imports
- Follow established patterns
- Use project's preferred packages

### Project Patterns
```kotlin
// TV Material3 Components
import androidx.tv.material3.Button
import androidx.tv.material3.Surface

// Standard Compose
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text

// Project-specific
import com.elite.iptv.dvr.viewmodel.MainViewModel
```

## 4. Static Analysis Checklist

Before finalizing any file, verify:

### Import Completeness
- [ ] All Compose UI classes from `androidx.compose.*`
- [ ] Graphics classes from `androidx.compose.ui.graphics.*`
- [ ] TV Material3 from `androidx.tv.material3.*`
- [ ] Project classes from `com.elite.iptv.dvr.*`

### API Compatibility
- [ ] No `ThreadLocal.withInitial`
- [ ] No Java 8+ features requiring API 26+
- [ ] Anonymous object pattern for ThreadLocal

### Code Structure
- [ ] No duplicate imports
- [ ] Consistent import organization
- [ ] All referenced classes imported

## 5. Common Issues & Solutions

### Unresolved Reference: TileMode
```kotlin
// Missing import
import androidx.compose.ui.graphics.TileMode

// Usage
brush = Brush.horizontalGradient(
    colors = listOf(...),
    tileMode = TileMode.Clamp
)
```

### Unresolved Reference: Brush
```kotlin
// Missing import
import androidx.compose.ui.graphics.Brush

// Usage
.background(
    brush = Brush.linearGradient(...)
)
```

### ThreadLocal Compilation Error
```kotlin
// Wrong (API 26+)
private val sdf = ThreadLocal.withInitial { SimpleDateFormat(...) }

// Right (API 21+)
private val sdf = object : ThreadLocal<SimpleDateFormat>() {
    override fun initialValue(): SimpleDateFormat = SimpleDateFormat(...)
}
```

## 6. File Template

```kotlin
@file:OptIn(ExperimentalTvMaterial3Api::class)

package com.elite.iptv.dvr.ui.screens

// Android/AndroidX imports
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TileMode
import androidx.tv.material3.Surface

// Project imports
import com.elite.iptv.d.viewmodel.ViewModel

@Composable
fun MyScreen() {
    // Implementation
}
```

## Why This Matters

- **TileMode Fix**: Prevents "Unresolved reference" errors in gradient code
- **ThreadLocal Fix**: Ensures app works on older Android TV devices (pre-Oreo)
- **Import Consistency**: Prevents compilation issues and maintains clean code
- **API 21 Support**: Maximum device compatibility for Android TV ecosystem
