# Android TV App UI Guidelines
# Based on Spyro-Soft TV UX/UI Best Practices (Sections 1, 2, 3, 5)

## Quick Reference for ELITE IPTV DVR

### Typography Standards
- **Minimum 22px font size** for body text
- **Roboto font** recommended (Google-optimized for TV)
- **Sans-serif fonts** for labels and longer text
- **Thicker typefaces** with 20-30% increased line spacing
- **Wider character spacing** for distance readability

### Layout & Spacing
- **Android TV safe areas**: 27px top/bottom, 48px left/right minimum
- **Generous white space** - most powerful design tool
- **Single primary purpose** per screen
- **Large, clear content tiles** with minimal text overlay
- **Content front and centre** - eliminate non-essential elements

### D-Pad Navigation
- **Clear focus states** with obvious visual distinction
- **Predictable up/down/left/right movement patterns**
- **Consistent spacing** between focusable elements
- **Accessible back button** - always returns without confirmations
- **Avoid blocking exits** with confirmation screens

## Current EPG Guide Analysis vs. Guidelines

### What's Working Well
- **Font sizes**: Title 26sp, body 14-16sp (meets 22px minimum)
- **Roboto usage**: Default Android font
- **Focus states**: Clear color changes and scaling
- **Safe areas**: 20dp padding (close to 27px minimum)
- **Single purpose**: TV guide focuses on program browsing

### Areas for Improvement

#### Typography
```kotlin
// Current (good)
fontSize = 26.sp  // Title
fontSize = 14.sp  // Body

// Better for 10-foot experience
fontSize = 28.sp  // Title (increase)
fontSize = 16.sp  // Body (increase)
lineHeight = 20.sp // Add line height for body text
```

#### Spacing & White Space
```kotlin
// Current
padding(horizontal = 20.dp, vertical = 14.dp)
Spacer(Modifier.height(12.dp))

// Better - more generous spacing
padding(horizontal = 27.dp, vertical = 18.dp) // Meet safe area
Spacer(Modifier.height(16.dp))
```

#### Focus States
```kotlin
// Current focus handling
colors = ClickableSurfaceDefaults.colors(
    containerColor = Color(0xFF1E1E1E),
    focusedContainerColor = Color(0xFF2E2E2E),
)

// Enhanced focus with more visual distinction
colors = ClickableSurfaceDefaults.colors(
    containerColor = Color(0xFF1E1E1E),
    focusedContainerColor = Color(0xFFF89344),
    focusedBorderColor = Color.White,
    focusedBorderWidth = 2.dp,
)
```

#### Safe Area Compliance
```kotlin
// Current header padding
.padding(horizontal = 20.dp, vertical = 14.dp)

// Android TV compliant
.padding(horizontal = 27.dp, vertical = 18.dp)
```

## Implementation Checklist

### High Priority
- [ ] Increase font sizes to 28sp (titles) and 16sp (body)
- [ ] Add 20-30% increased line spacing for body text
- [ ] Ensure 27px/48px safe area margins
- [ ] Enhance focus state visual distinction
- [ ] Add more generous white space between sections

### Medium Priority
- [ ] Test on actual TV from 3+ meters distance
- [ ] Verify D-pad navigation flows logically
- [ ] Ensure back button works consistently without confirmations
- [ ] Check text readability in different lighting conditions

### Low Priority
- [ ] Add character spacing for improved distance readability
- [ ] Test on older TV models for overscan issues
- [ ] Validate color contrast for different display technologies

## Testing Guidelines

### Distance Testing
- **Test from 3+ meters** away from screen
- **Simulate family viewing** with distractions
- **Test in different lighting**: morning, evening, night

### Device Testing
- **Real TV devices** (not just emulators)
- **Multiple TV models** including older/budget TVs
- **Different screen sizes** and display technologies

### Navigation Testing
- **D-pad only** - no touch interaction
- **Predictable movement** - up/down/left/right makes sense
- **Focus visibility** - selected element obvious from distance

## Code Examples

### Enhanced Typography
```kotlin
Text(
    text = selection.listing.title,
    color = Color.White,
    fontSize = 28.sp, // Increased from 26sp
    fontWeight = FontWeight.Bold,
    lineHeight = 32.sp, // Added line height
    maxLines = 1,
    overflow = TextOverflow.Ellipsis,
)
```

### Better Focus States
```kotlin
Surface(
    onClick = onClick,
    modifier = Modifier
        .focusRequester(focusRequester)
        .onFocusChanged { if (it.isFocused) onClick() }
        .border(
            width = if (isSelected) 3.dp else 0.dp,
            color = Color.White,
            shape = RoundedCornerShape(4.dp)
        ),
    shape = ClickableSurfaceDefaults.shape(shape = RoundedCornerShape(4.dp)),
    colors = ClickableSurfaceDefaults.colors(
        containerColor = Color(0xFF1E1E1E),
        focusedContainerColor = Color(0xFFF89344),
    ),
)
```

### Safe Area Compliance
```kotlin
Column(
    modifier = Modifier
        .fillMaxSize()
        .background(Color.Black)
        .padding(
            start = 27.dp,  // Android TV safe area
            end = 27.dp,
            top = 27.dp,
            bottom = 27.dp
        )
) {
    // Content here
}
```

## Gradients and Branding

### Color Gradients
- **Horizontal gradients** for headers and navigation
- **Vertical gradients** for details panes and cards
- **Brand colors**: #F89344 (orange), #FF6B35 (orange-red), #C73E1D (red)
- **Use subtle gradients** (30-40% opacity) for backgrounds
- **Strong gradients** for focus states and branding elements

### Logo Implementation
- **In-app logo**: 40dp box with gradient background and brand letter
- **App icon**: Adaptive icon with gradient foreground
- **Logo placement**: Top-left of headers, consistent across screens
- **Logo colors**: White text on brand gradient background

### Gradient Examples

#### Header Gradient
```kotlin
.background(
    brush = Brush.horizontalGradient(
        colors = listOf(
            Color(0xFF1A1A1A),
            Color(0xFF2A2A2A),
            Color(0xFF1A1A1A)
        ),
        tileMode = TileMode.Clamp
    )
)
```

#### Details Pane Gradient
```kotlin
.background(
    brush = Brush.verticalGradient(
        colors = listOf(
            Color(0xFF1A1A1A),
            Color(0xFF111317),
            Color(0xFF0A0A0A)
        ),
        startY = 0f,
        endY = 170f
    )
)
```

#### Logo Gradient
```kotlin
.background(
    brush = Brush.linearGradient(
        colors = listOf(
            Color(0xFFF89344),
            Color(0xFFFF6B35),
            Color(0xFFC73E1D)
        ),
        start = Offset(0f, 0f),
        end = Offset(40f, 40f)
    )
)
```

## Next Steps

1. **Apply typography improvements** to EPG guide
2. **Enhance focus states** for better visibility
3. **Ensure safe area compliance** throughout app
4. **Test on real TV devices** from viewing distance
5. **Validate D-pad navigation** flows logically
6. **Add gradients to other screens** for consistent branding
7. **Test logo visibility** from 3+ meters distance
