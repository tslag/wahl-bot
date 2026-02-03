import { useEffect, useState } from 'react';
import authService from '../services/authService';

import '../css/SideBar.css'
import '../css/AddProgramModal.css'
import LoadingStatus from './LoadingStatus';
import { useProgramContext } from '../contexts/ProgramContext';
import { API_BASE_URL } from "../util";

function SideBar() {

    const {selectedProgram, setSelectedProgram, programList, getProgramList, removeFromChatHistory} = useProgramContext();
    const programExists = programList.length > 0;

    const [programAction, setProgramAction] = useState("");

    // for uploading a new program
    const [file, setFile] = useState(null);
    const [programName, setProgramName] = useState("");

    // for ingesting new program
    const [showModal, setShowModal] = useState(false);
    const [taskId, setTaskId] = useState(null);
    const [taskStatus, setTaskStatus] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    // for deleting a program
    const [deleteModal, setDeleteModal] = useState(false);
    const [deleteProgramName, setDeleteProgramName] = useState("");

    useEffect(() => {
        let pollIntervall;

        if (taskId && taskStatus === "processing") {
            pollIntervall = setInterval(() => {
                pollTaskStatus(taskId)
            }, 5000)
        }

        return () => {
            if (pollIntervall) {
                clearInterval(pollIntervall)
            }
        }
    }, [taskId, taskStatus])

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        setFile(file);
    };

    const handleNewProgramSubmit = async (e) => {
        e.preventDefault();

        if (!file || !programName) {
            alert("Please select a program and a file to upload.");
            return;
        }

        setProgramAction("ingest");
        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('program_name', programName);
        formData.append('file', file);

        try {
            await authService.apiRequest(`${API_BASE_URL}/program/upload`, { method: 'POST', body: formData });
        } catch (err) {
            setError(`Failed to upload program: ${err.response?.data?.message || err.message}`);
            console.log(err);
            console.error('Error uploading failed:', err);
            alert(`Upload failed: ${err.response?.data?.message || err.message}`);
        }

        try {
            const resp = await authService.apiRequest(`${API_BASE_URL}/program/ingest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ program_name: programName })
            });
            const response = await resp.json();
            const { task_id, status } = response;
            setTaskId(task_id);
            setTaskStatus(status);
            pollTaskStatus(task_id);
            setShowModal(false)

        } catch (error) {
            setLoading(false);
            setError(error?.message || "An error occurred while ingesting the program.");
            console.log(error);
            console.error('Error ingesting program:', error);
        }
    }

    const handleDeleteProgram = async (programName) => {
        try {
            setLoading(true);
            setProgramAction("delete")
            const resp = await authService.apiRequest(`${API_BASE_URL}/program/delete/${programName}`, { method: 'DELETE' });
            const response = await resp.json();
            const { task_id, status, error: taskError } = response;
            setTaskId(task_id);
            setTaskStatus(status)
            pollTaskStatus(task_id);
            removeFromChatHistory(programName);
            setDeleteModal(false);

        } catch (error) {
            setLoading(false);
            setError(error?.message || "An error occurred while deleting the program.");
            console.log(error);
            console.error('Error deleting program:', error);
        }
    }

    const pollTaskStatus = async (id) => {
        try {
            const resp = await authService.apiRequest(`${API_BASE_URL}/tasks/${id}`, { method: 'GET' });
            const response = await resp.json();
            const {status, task_id, error: taskError} = response
            setTaskStatus(status)

            if (status === "completed" && task_id) {
                await getProgramList();
                setLoading(false)
                setTaskStatus("completed")
                setProgramAction("")
                setProgramName("")
            } else if (status == "failed" || taskError) {
                setError(taskError || "Program task failed")
                setLoading(false)
                setProgramAction("")
                setSelectedProgram("")
            }

        } catch (e) {
            if (e.response?.status !== 404) {
                setError(`Failed to check Program status: ${e.message}`)
                setLoading(false)
                setProgramAction("")
                setSelectedProgram("")
            }
        }
    }

    return (
        <>
        <aside className="sidebar">
            <div className="sidebar-header">
                <h2>Program List</h2>
                <p className="app-instruction">
                    Upload a program and learn all about it
                </p>

            </div>

            <div className="program-list">
                <div className='program-item'>
                    <button className={`add-program-item ${selectedProgram === "Add Program" ? "selected" : ""}`}
                        onClick={() => setShowModal(true)}>
                        + Add Program
                    </button>
                </div>
                {!programExists ? <p>Add a program to get started</p> : programList.map((program) => (
                    <div className='program-item' key={program.name}>
                        <button className={`program-item ${selectedProgram === program.name ? "selected" : ""}`}
                            onClick={() => { setSelectedProgram(program.name); }}>
                            {program.name}
                        </button>
                        <button className="delete-program-btn"
                            onClick={(e) => {
                                e.stopPropagation();
                                setDeleteProgramName(program.name);
                                setDeleteModal(true);
                            }}>
                            🗑️
                        </button>
                    </div>
                ))
                }


            </div>
        </aside>

        {/* Modal Popup */}
        {showModal && (
            <div className="modal-overlay" onClick={() => setShowModal(false)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                    <h2>Add New Program</h2>
                    <form onSubmit={handleNewProgramSubmit}>
                        <input type="text" placeholder="Program name" className="modal-input"
                            onChange={(e) => setProgramName(e.target.value)}
                            value={programName}
                        />
                        <input type="file"
                            onChange={handleFileChange}
                            className="modal-input"
                            accept=".pdf"
                            />
                        <div className="modal-actions">
                            <button type="submit" className="btn-submit" onClick={() => {
                                setSelectedProgram(programName)
                            }}>Upload</button>
                            <button type="button"  className="btn-cancel" onClick={() => {
                                setShowModal(false);
                                setFile(null);
                                setProgramName(""); }}>Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        )}

        {/* Delete Confirmation Modal */}
        {deleteModal && (
            <div className="modal-overlay" onClick={() => setDeleteModal(false)}>
                <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                    <h2>Confirm Delete Program: {deleteProgramName}</h2>
                    <div className="modal-actions">
                        <button type="submit" className="btn-delete" onClick={() => {
                            handleDeleteProgram(deleteProgramName);
                            setDeleteProgramName("");
                            if (selectedProgram === deleteProgramName) {
                                setSelectedProgram("");
                            }
                        }}>Delete</button>
                        <button type="button"  className="btn-cancel" onClick={() => {
                            setDeleteModal(false);
                            setDeleteProgramName("");
                        }}>Cancel</button>
                    </div>
                </div>
            </div>
        )}

        {loading && <LoadingStatus programName={programName} programAction={programAction} />}

    </>
    );
}

export default SideBar
