"use client";

import React from "react";

export interface BubbleShellProps {
  side: "left" | "right";
  avatar: React.ReactNode;
  avatarBorder?: string;
  avatarBg?: string;
  children: React.ReactNode;
  timestamp?: string;
  maxWidth?: string;
}

export default function BubbleShell({
  side,
  avatar,
  avatarBorder,
  avatarBg = "bg-[#0c0c14]",
  children,
  timestamp,
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
          {timestamp && (
            <p className="text-xs mt-1 text-white/45">
              {new Date(timestamp).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-end">
      <div className={`${maxWidth} flex flex-col items-end`}>
        {children}
        {timestamp && (
          <p className="text-xs mt-1 text-indigo-300">
            {new Date(timestamp).toLocaleTimeString()}
          </p>
        )}
      </div>
      {avatarCircle}
    </div>
  );
}
