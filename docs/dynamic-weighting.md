# Dynamic Film Weighting

Customize which films get priority in your festival schedule based on release year and special events.

## Overview

You can adjust film priorities based on:
- **Release Year**: Boost or reduce priority for films from specific years
- **Special Events**: Increase priority for films with Q&As, director appearances, etc.

These adjustments help you focus on rare opportunities (like classic films or special events) or avoid films you can see elsewhere.

## Configuration

Edit `config/preferences.yaml` to set your preferences:

```yaml
# Boost classic films from specific years
year_weights:
  1960: 0.3   # Higher priority for 1960 films
  1985: 0.2   # Higher priority for 1985 films

# Boost films with special events
special_notes_weight: 0.5
```

**How values work:**
- Positive values (e.g., `0.3`, `0.5`) = higher priority
- Negative values (e.g., `-0.2`) = lower priority
- `0` = no adjustment

## Common Scenarios

### Prioritize Classic Cinema

Focus on films from important years in cinema history:

```yaml
year_weights:
  1960: 0.5  # French New Wave
  1975: 0.4  # New Hollywood
  1985: 0.3  # Independent cinema boom
special_notes_weight: 0.0
```

**Result:** Classic films will be prioritized over recent releases.

---

### Maximize Special Experiences

Never miss Q&As, director appearances, and special screenings:

```yaml
year_weights: {}
special_notes_weight: 0.8
```

**Result:** Films with special events get strong priority.

---

### See Rare Films First

Deprioritize recent films you might catch elsewhere, focus on older or harder-to-find films:

```yaml
year_weights:
  2024: -0.2
  2025: -0.3
special_notes_weight: 0.3
```

**Result:** Older films and special events are prioritized over recent releases.

---

### Focus on a Specific Era

Heavily prioritize films from the 1990s:

```yaml
year_weights:
  1990: 0.6
  1991: 0.6
  1992: 0.6
  1993: 0.6
  1994: 0.6
  1995: 0.6
  1996: 0.6
  1997: 0.6
  1998: 0.6
  1999: 0.6
special_notes_weight: 0.2
```

**Result:** 90s films dominate your schedule, with special events as a nice bonus.

---

### Balanced Approach

Slight preference for classics and special events:

```yaml
year_weights:
  1960: 0.2
  1985: 0.15
special_notes_weight: 0.3
```

**Result:** Moderate boost to classics and special events while staying flexible.

## Tips

- **Start small**: Use small adjustments (0.2-0.3) and see how they affect your schedule
- **Combine strategically**: Year weights and special events work together
- **Think about access**: Use negative weights for films you can stream or see later
- **Experiment**: Try different configurations and run the solver to see what works best

