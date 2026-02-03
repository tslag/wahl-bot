import '../css/LoadingStatus.css'

function LoadingStatus({programName, programAction}) {
    const getTitle = () => {
        if (programAction === 'delete') {
            return `Deleting Program: ${programName}`;
        }
        return `Ingesting Program: ${programName}`;
    };

    const getMessage = () => {
        if (programAction === 'delete') {
            return 'Please wait while your program is being deleted...';
        }
        return 'Please wait while your program is ingested...';
    };

    return <div className="loading-container">
        <div className="loading-content">
        <h2>{getTitle()}</h2>

        <div className="loading-animation">
            <div className="spinner"></div>
        </div>

        <p className="loading-info">
            {getMessage()}
        </p>
        </div>
    </div>
}

export default LoadingStatus
