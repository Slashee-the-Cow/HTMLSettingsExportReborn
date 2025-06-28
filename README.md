# HTML Settings Export Reborn
A continuation of [Cura HTML Doc](https://github.com/5axes/CuraHtmlDoc) by [5axes](https://github.com/5axes/)  
Initial plugin based on [CuraSettingsWriter](https://github.com/johnnygizmo/CuraSettingsWriter) by Johnny Matthews
## Have you ever wished you had a nice looking web page with your print quality settings?
No? Well don't knock it until you try it! It can be a pretty handy reference. If I do a really good looking print, I'll print the web page and keep it nearby so I know how to repeat my awesome feat!

I suppose you can keep it with your gcode files as a reference. Or send it to other people so they can easily see what changes are the key to your success. Maybe you already have a website and you can post it straight there? Tile two pages side by side so you can see the difference between two of your prints?

This is the sort of thing that probably has a million and one uses, even if I can only name five of them. You lovely people out there are much better at coming up with ways to use things than I am, so I'm sure you'll figure out the other 999,996 uses.

### What cool things does it do?
- Search the settings if you're looking for a specific thing!
- Compare two different profiles side by side. Even for different printers!
- Filter the output to only show settings that have been changed from the default.
- Hide/show disabled settings to get rid of clutter of stuff that doesn't apply.
- Hover your mouse over a setting name to get what Cura calls it internally.

### So how do I use it?
Just set up your print, then open the *Extensions* menu, go down to *HTML Settings Export* then click *Export settings*.

To compare two profiles, activate the first profile, then in the *HTML Settings Export* menu click *Select first profile for comparison*. Then activate your other profile and select *Export comparison with first profile*.

---
### Got feedback? Feature suggestion? Find a bug? Just did something awesome and want to share it with someone?
I want to know about it! Just jump by the [GitHub repo](https://github.com/slashee-the-cow/htmlsettingsexportreborn/) and drop me a line.

---
### Version History
#### v1.2.1:
- Minor bug fixes.
#### v1.2.0:
- **Compare two profiles side by side!** (That's the headliner this time.)
- Exported web pages have had their file size reduced by about 50%.
- Printer name added to page.
#### v1.1.0:
- **Added setting search function to output page!** (That's the headliner here.)
- Buttons for hiding/showing sets of settings now change their text based on state.
#### v1.0.0:
*Serious* refactor of the code. Basically the way it actually gets the settings stayed the same and got wrapped in all new stuff.

**So what's better?**
- Replaced toolbar icon for exporting the settings with a menu entry.
- Significant improvements to the look and feel of the output page.
- Settings for all extruders now appear next to each other in the same table.
- Can collapse/expand setting categories so you can focus on the important bits.
- Setting values will now indicate Cura's warning values as well as well as the invalid values.
- Page now has a sticky header with buttons for toggling setting visibility always available.
- The visibility setting for user changed settings will now make it show only user changed settings.
- Better table formatting should make things easier to read.
- Extensive changes on the internal code should make it more reliable and a bit speedier.
  
**So what's not better?**  
- Minimum Cura version is now 5.0 due to removal of Qt 5 components.
- Autosave feature has been removed to make sure this process doesn't get in the way of saving gcode.

### Known Issues
- Formatting of the "machine settings" section might result in narrow columns of the setting values with text wrapping across several lines.