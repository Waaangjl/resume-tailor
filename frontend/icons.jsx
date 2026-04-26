/* Icons — clean monoline SVG, 1.5px stroke, 20×20 viewBox.
   Designed cohesively to match the Plan B aesthetic.
*/
const Icon = ({ name, size = 18, stroke = 1.5, style = {}, className = '' }) => {
  const props = {
    width: size, height: size, viewBox: '0 0 20 20',
    fill: 'none', stroke: 'currentColor',
    strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round',
    style, className,
  };
  switch (name) {
    case 'logo':       // resume / sparkle mark
      return (
        <svg {...props} viewBox="0 0 22 22" strokeWidth={1.6}>
          <path d="M5.5 3h7l4 4v12a0 0 0 0 1 0 0H5.5a0 0 0 0 1 0 0V3z" />
          <path d="M12.5 3v4h4" />
          <path d="M14.5 13.2l1 .4-1 .4-.4 1-.4-1-1-.4 1-.4.4-1zM8 10l.7 1.6L10.3 12l-1.6.7L8 14.3l-.7-1.6L5.7 12l1.6-.4z" fill="currentColor" stroke="none" />
        </svg>
      );
    case 'arrow-right': return (<svg {...props}><path d="M4 10h12M11 5l5 5-5 5"/></svg>);
    case 'arrow-left':  return (<svg {...props}><path d="M16 10H4M9 5L4 10l5 5"/></svg>);
    case 'chevron-right': return (<svg {...props}><path d="M8 5l5 5-5 5"/></svg>);
    case 'check':       return (<svg {...props}><path d="M4 10.5l3.5 3.5L16 6"/></svg>);
    case 'x':           return (<svg {...props}><path d="M5 5l10 10M15 5L5 15"/></svg>);
    case 'plus':        return (<svg {...props}><path d="M10 4v12M4 10h12"/></svg>);
    case 'edit':        return (<svg {...props}><path d="M3 17h3.5L16 7.5 13 4.5 3.5 14 3 17z"/><path d="M12 5.5l3 3"/></svg>);
    case 'trash':       return (<svg {...props}><path d="M3.5 5.5h13M8 5.5V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.5M5 5.5v11a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-11"/><path d="M8.5 9v5M11.5 9v5"/></svg>);
    case 'copy':        return (<svg {...props}><rect x="6.5" y="6.5" width="9" height="11" rx="1.5"/><path d="M3.5 13.5V4a1 1 0 0 1 1-1h8"/></svg>);
    case 'download':    return (<svg {...props}><path d="M10 3v10M5 9l5 4 5-4"/><path d="M3.5 16h13"/></svg>);
    case 'upload':      return (<svg {...props}><path d="M10 14V4M5 8l5-4 5 4"/><path d="M3.5 16h13"/></svg>);
    case 'file':        return (<svg {...props}><path d="M5 2.5h7l4 4V17a0 0 0 0 1 0 .5H5a0 0 0 0 1 0-.5V2.5z"/><path d="M12 2.5v4h4"/></svg>);
    case 'file-text':   return (<svg {...props}><path d="M5 2.5h7l4 4V17a.5 .5 0 0 1 -.5 .5h-11a.5 .5 0 0 1 -.5-.5V2.5z"/><path d="M12 2.5v4h4M7.5 11h5M7.5 13.5h5"/></svg>);
    case 'link':        return (<svg {...props}><path d="M8 12.5l4-5"/><path d="M11 5.5l1-1a3 3 0 1 1 4.2 4.2l-2 2"/><path d="M9 14.5l-1 1a3 3 0 1 1-4.2-4.2l2-2"/></svg>);
    case 'sparkles':    return (<svg {...props}><path d="M10 3l1.4 3.6L15 8l-3.6 1.4L10 13l-1.4-3.6L5 8l3.6-1.4z"/><path d="M15.5 13l.6 1.5 1.4.5-1.4.5-.6 1.5-.6-1.5L13.5 15l1.4-.5z"/></svg>);
    case 'palette':     return (<svg {...props}><path d="M10 17a7 7 0 1 1 7-7 3 3 0 0 1-3 3h-1.5a1.5 1.5 0 0 0-1 2.6c.4.4.5 1 .2 1.5A1.5 1.5 0 0 1 10 17z"/><circle cx="6.5" cy="9" r=".7" fill="currentColor"/><circle cx="9" cy="6" r=".7" fill="currentColor"/><circle cx="13" cy="6" r=".7" fill="currentColor"/><circle cx="14.5" cy="9" r=".7" fill="currentColor"/></svg>);
    case 'briefcase':   return (<svg {...props}><rect x="3" y="6" width="14" height="10" rx="1.5"/><path d="M7 6V4.5A1.5 1.5 0 0 1 8.5 3h3A1.5 1.5 0 0 1 13 4.5V6"/><path d="M3 10.5h14"/></svg>);
    case 'user':        return (<svg {...props}><circle cx="10" cy="7" r="3"/><path d="M4 17a6 6 0 0 1 12 0"/></svg>);
    case 'mic':         return (<svg {...props}><rect x="8" y="3" width="4" height="9" rx="2"/><path d="M5.5 10a4.5 4.5 0 0 0 9 0M10 14.5V17"/></svg>);
    case 'list':        return (<svg {...props}><path d="M7 5h10M7 10h10M7 15h10"/><circle cx="3.5" cy="5" r=".7" fill="currentColor"/><circle cx="3.5" cy="10" r=".7" fill="currentColor"/><circle cx="3.5" cy="15" r=".7" fill="currentColor"/></svg>);
    case 'wand':        return (<svg {...props}><path d="M4 16l8-8"/><path d="M11 5l1.5-1.5L14 5l-1.5 1.5zM14 8l1.5-1.5L17 8l-1.5 1.5z"/></svg>);
    case 'eye':         return (<svg {...props}><path d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z"/><circle cx="10" cy="10" r="2.2"/></svg>);
    case 'tag':         return (<svg {...props}><path d="M3 3h6l8 8-6 6-8-8z"/><circle cx="6.5" cy="6.5" r="1" fill="currentColor"/></svg>);
    case 'archive':     return (<svg {...props}><rect x="3" y="4" width="14" height="3" rx="0.5"/><path d="M4 7v9a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7"/><path d="M8 11h4"/></svg>);
    case 'settings':    return (<svg {...props}><circle cx="10" cy="10" r="2.5"/><path d="M10 1.5v2M10 16.5v2M3.5 10h-2M18.5 10h-2M5 5l-1.4-1.4M16.4 16.4L15 15M5 15l-1.4 1.4M16.4 3.6L15 5"/></svg>);
    case 'overleaf':    return (<svg {...props}><path d="M10 3a7 7 0 1 0 6.5 4.5L13 10h4"/></svg>);
    case 'spark':       return (<svg {...props}><path d="M10 2v4M10 14v4M2 10h4M14 10h4M4.5 4.5l2.5 2.5M13 13l2.5 2.5M4.5 15.5L7 13M13 7l2.5-2.5"/></svg>);
    case 'undo':        return (<svg {...props}><path d="M5 8h7a4 4 0 0 1 0 8H8"/><path d="M8 5L5 8l3 3"/></svg>);
    default: return null;
  }
};

window.Icon = Icon;
