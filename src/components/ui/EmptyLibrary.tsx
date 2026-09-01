import React, { ReactNode } from "react";
import { Plus } from "lucide-react";
import { Button } from "./Button";

interface EmptyLibraryProps {
  title?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyLibrary({ title = "No items found", icon, action }: EmptyLibraryProps) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '4rem 2rem',
      textAlign: 'center',
      color: 'var(--color-secondary-text)',
      backgroundColor: 'var(--color-surface)',
      borderRadius: '12px',
      border: '1px dashed var(--color-border)',
      margin: '2rem 0',
      minHeight: '200px'
    }}>
      {icon && (
        <div style={{ 
          marginBottom: '1rem', 
          color: 'var(--color-tertiary-text, #888)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          backgroundColor: 'var(--color-background, #f5f5f5)'
        }}>
          {icon}
        </div>
      )}
      <h3 style={{
        fontSize: '1.125rem',
        fontWeight: 500,
        color: 'var(--color-primary-text, #111)',
        margin: '0 0 0.5rem 0'
      }}>
        {title}
      </h3>
      {action && (
        <div style={{ marginTop: '1.25rem' }}>
          {action}
        </div>
      )}
    </div>
  );
}

interface UploadCtaProps {
  onClick: () => void;
}

export function UploadCta({ onClick }: UploadCtaProps) {
  return (
    <Button onClick={onClick} variant="primary">
      <Plus size={16} style={{ marginRight: '8px' }} />
      Upload Memory
    </Button>
  );
}
