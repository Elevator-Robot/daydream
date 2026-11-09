import React, { useCallback, useEffect, useRef } from 'react';
import { Select as RadixSelect } from '@radix-ui/themes';

// One dropdown policy for every dashboard selection. Popper normally flips to
// the top near a viewport edge; keep it below and make its option list scroll.
const Trigger = React.forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<typeof RadixSelect.Trigger>>(
  function Trigger({ onPointerDownCapture, onKeyDownCapture, ...props }, ref) {
    const makeRoom = (button: HTMLButtonElement) => {
      if (window.innerHeight - button.getBoundingClientRect().bottom < Math.min(260, window.innerHeight * .4)) {
        button.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
      }
    };
    return <RadixSelect.Trigger {...props} ref={ref}
      onPointerDownCapture={event => { onPointerDownCapture?.(event); if (!event.defaultPrevented) makeRoom(event.currentTarget); }}
      onKeyDownCapture={event => { onKeyDownCapture?.(event); if (!event.defaultPrevented && ['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) makeRoom(event.currentTarget); }}/>;
  },
);

const Content = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<typeof RadixSelect.Content>>(
  function Content({ style, className, ...props }, forwardedRef) {
    const element = useRef<HTMLDivElement | null>(null);
    const update = useCallback(() => {
      const node = element.current;
      if (node) node.style.setProperty('--daydream-select-space', `${Math.max(44, window.innerHeight - node.getBoundingClientRect().top - 12)}px`);
    }, []);
    const setRef = useCallback((node: HTMLDivElement | null) => {
      element.current = node;
      if (typeof forwardedRef === 'function') forwardedRef(node);
      else if (forwardedRef) forwardedRef.current = node;
      if (node) requestAnimationFrame(update);
    }, [forwardedRef, update]);
    useEffect(() => {
      window.addEventListener('resize', update); window.addEventListener('scroll', update, true);
      return () => { window.removeEventListener('resize', update); window.removeEventListener('scroll', update, true); };
    }, [update]);
    return <RadixSelect.Content {...props} ref={setRef} position="popper" side="bottom" align="start" sideOffset={6}
      avoidCollisions={false} className={`daydream-select-menu ${className ?? ''}`}
      style={{ ...style, maxHeight: 'min(320px, var(--daydream-select-space, 45dvh))' }}/>;
  },
);

export const Select = { ...RadixSelect, Trigger, Content };
