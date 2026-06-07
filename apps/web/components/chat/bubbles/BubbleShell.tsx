"use client";

import React from "react";

export interface BubbleShellProps {
  side: "left" | "right";
  avatar: React.ReactNode;
  avatarBorder?: string;
  avatarBg?: string;
  children: React.ReactNode;
  timestamp?: string;
  actions?: React.ReactNode;
  maxWidth?: string;
}

export default function BubbleShell({
  side,
  avatar,
  avatarBorder,
  avatarBg = "bg-[#0c0c14]",
  children,
  timestamp,
  actions,
  maxWidth = "max-w-[78%]",
}: BubbleShellProps): React.JSX.Element {
  const avatarCircle = (
    <div
      className={`w-7 h-7 rounded-full ${avatarBg} flex items-center justify-center shrink-0 mt-1${
        avatarBorder ? ` border ${avatarBorder}` : ""
      }${side === "left" ? " mr-3" : " ml-3"}`}
    >
      {avatar}
    </div>
  );

  if (side === "left") {
    return (
      <div className="flex justify-start">
        {avatarCircle}
        <div className={`${maxWidth} flex flex-col items-start`}>
          {children}
          {(timestamp ?? actions) && (
            <div className="flex items-center gap-1.5 mt-1">
              {timestamp && (
                <span className="text-xs text-white/45">
                  {new Date(timestamp).toLocaleTimeString()}
                </span>
              )}
              {actions}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-end">
      <div className={`${maxWidth} flex flex-col items-end`}>
        {children}
        {(timestamp ?? actions) && (
          <div className="flex items-center gap-1.5 mt-1">
            {timestamp && (
              <span className="text-xs text-indigo-300">
                {new Date(timestamp).toLocaleTimeString()}
              </span>
            )}
            {actions}
          </div>
        )}
      </div>
      {avatarCircle}
    </div>
  );
}
